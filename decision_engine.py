"""Time-aware, leak-resistant AQI modeling for the daily decision view.

All training values are Open-Meteo/CAMS retrospective estimates, not station
observations. Missing hourly samples are left missing; the hourly reindex only
makes gaps explicit and never supplies replacement measurements.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st
from sklearn.calibration import calibration_curve
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, mean_absolute_error, roc_auc_score
from sklearn.utils.class_weight import compute_sample_weight

HORIZONS = (6, 12, 24)
REGRESSION_HORIZONS = (1, 6, 12, 24)

WEATHER_FEATURES = (
    "temperature_2m",
    "relative_humidity_2m",
    "wind_speed_10m",
    "precipitation",
    "surface_pressure",
    "uv_index",
    "hours_since_rain",
    "precipitation_sum_24h",
    "wind_mean_6h",
    "pressure_change_3h",
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
)
AQI_FEATURES = (
    "us_aqi_lag_1h",
    "us_aqi_lag_3h",
    "us_aqi_lag_6h",
    "us_aqi_mean_6h",
    "us_aqi_mean_24h",
    "pm25_lag_1h",
    "pm25_lag_6h",
    "pm25_mean_6h",
)
FEATURES = WEATHER_FEATURES + AQI_FEATURES
AQI_LAG_FEATURES = (
    "us_aqi_lag_1h",
    "us_aqi_lag_3h",
    "us_aqi_lag_6h",
    "us_aqi_mean_6h",
    "us_aqi_mean_24h",
)

FEATURE_LABELS = {
    "temperature_2m": "Nhiệt độ",
    "relative_humidity_2m": "Độ ẩm",
    "wind_speed_10m": "Gió hiện tại",
    "precipitation": "Mưa trong giờ",
    "surface_pressure": "Áp suất",
    "uv_index": "Chỉ số UV",
    "hours_since_rain": "Thời gian từ trận mưa gần nhất",
    "precipitation_sum_24h": "Tổng mưa 24 giờ",
    "wind_mean_6h": "Gió trung bình 6 giờ",
    "pressure_change_3h": "Thay đổi áp suất 3 giờ",
    "hour_sin": "Giờ trong ngày",
    "hour_cos": "Giờ trong ngày",
    "weekday_sin": "Ngày trong tuần",
    "weekday_cos": "Ngày trong tuần",
    "us_aqi_lag_1h": "AQI giờ trước",
    "us_aqi_lag_3h": "AQI 3 giờ trước",
    "us_aqi_lag_6h": "AQI 6 giờ trước",
    "us_aqi_mean_6h": "AQI trung bình 6 giờ",
    "us_aqi_mean_24h": "AQI trung bình 24 giờ",
    "pm25_lag_1h": "PM₂.₅ giờ trước",
    "pm25_lag_6h": "PM₂.₅ 6 giờ trước",
    "pm25_mean_6h": "PM₂.₅ trung bình 6 giờ",
}


def _to_hourly_grid(weather: pd.DataFrame, air: pd.DataFrame) -> pd.DataFrame:
    weather_columns = [
        "temperature_2m", "relative_humidity_2m", "wind_speed_10m",
        "precipitation", "surface_pressure", "uv_index", "is_forecast",
    ]
    air_columns = ["us_aqi", "us_aqi_pm2_5", "pm2_5", "is_forecast"]
    weather = weather.copy() if weather is not None else pd.DataFrame()
    air = air.copy() if air is not None else pd.DataFrame()
    for frame in (weather, air):
        if "time" in frame:
            frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
            frame.dropna(subset=["time"], inplace=True)
    if weather.empty and air.empty:
        return pd.DataFrame(columns=["time", *weather_columns[:-1], *air_columns[:-1], "is_forecast"])

    def indexed(frame: pd.DataFrame, columns: list[str], suffix: str) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame(index=pd.DatetimeIndex([], name="time"))
        selected = frame[[name for name in ("time", *columns) if name in frame]].copy()
        if "is_forecast" not in selected:
            selected["is_forecast"] = False
        selected = selected.drop_duplicates("time", keep="last").set_index("time").sort_index()
        return selected.rename(columns={"is_forecast": f"is_forecast_{suffix}"})

    joined = indexed(weather, weather_columns, "weather").join(
        indexed(air, air_columns, "air"), how="outer"
    ).sort_index()
    if joined.empty:
        return joined.reset_index(names="time")
    start, end = joined.index.min().floor("h"), joined.index.max().ceil("h")
    joined = joined.reindex(pd.date_range(start, end, freq="h", name="time"))
    now = pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").tz_localize(None)
    flags = joined.get("is_forecast_weather", pd.Series(index=joined.index, dtype="boolean")).astype("boolean")
    air_flags = joined.get("is_forecast_air", pd.Series(index=joined.index, dtype="boolean")).astype("boolean")
    joined["is_forecast"] = (flags.fillna(False) | air_flags.fillna(False) | (joined.index > now))
    for column in (*weather_columns[:-1], *air_columns[:-1]):
        if column not in joined:
            joined[column] = np.nan
        joined[column] = pd.to_numeric(joined[column], errors="coerce")
    return joined.drop(columns=["is_forecast_weather", "is_forecast_air"], errors="ignore").reset_index()


def build_feature_frame(weather: pd.DataFrame, air: pd.DataFrame) -> pd.DataFrame:
    """Merge by exact timestamp and derive past-only predictors without filling gaps."""
    frame = _to_hourly_grid(weather, air)
    if frame.empty:
        return frame
    frame = frame.sort_values("time").set_index("time")
    idx = frame.index

    rain_hours: list[float] = []
    last_rain: int | None = None
    rain_history_known = False
    for position, amount in enumerate(frame["precipitation"].to_numpy(dtype=float)):
        if not np.isfinite(amount):
            # An unknown rain hour breaks an exact elapsed-time calculation.
            last_rain = None
            rain_history_known = False
            rain_hours.append(np.nan)
        elif amount > 0:
            last_rain = position
            rain_history_known = True
            rain_hours.append(0.0)
        elif last_rain is not None and rain_history_known:
            rain_hours.append(float(position - last_rain))
        else:
            rain_hours.append(np.nan)
    frame["hours_since_rain"] = rain_hours
    frame["precipitation_sum_24h"] = frame["precipitation"].rolling(24, min_periods=18).sum()
    frame["wind_mean_6h"] = frame["wind_speed_10m"].rolling(6, min_periods=4).mean()
    frame["pressure_change_3h"] = frame["surface_pressure"] - frame["surface_pressure"].shift(3)
    frame["hour_sin"] = np.sin(2 * math.pi * idx.hour / 24)
    frame["hour_cos"] = np.cos(2 * math.pi * idx.hour / 24)
    frame["weekday_sin"] = np.sin(2 * math.pi * idx.dayofweek / 7)
    frame["weekday_cos"] = np.cos(2 * math.pi * idx.dayofweek / 7)
    for lag in (1, 3, 6):
        frame[f"us_aqi_lag_{lag}h"] = frame["us_aqi"].shift(lag)
    frame["us_aqi_mean_6h"] = frame["us_aqi"].rolling(6, min_periods=4).mean()
    frame["us_aqi_mean_24h"] = frame["us_aqi"].rolling(24, min_periods=16).mean()
    frame["pm25_lag_1h"] = frame["pm2_5"].shift(1)
    frame["pm25_lag_6h"] = frame["pm2_5"].shift(6)
    frame["pm25_mean_6h"] = frame["pm2_5"].rolling(6, min_periods=4).mean()
    frame.index.name = "time"
    return frame.reset_index()


def _future_values(series: pd.Series, timestamps: pd.Series, steps: int, peak: bool) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    times = pd.to_datetime(timestamps).to_numpy(dtype="datetime64[ns]")
    output = np.full(len(values), np.nan, dtype=float)
    for i in range(len(values) - steps):
        future = values[i + 1 : i + steps + 1]
        future_times = times[i + 1 : i + steps + 1]
        expected = times[i] + np.arange(1, steps + 1).astype("timedelta64[h]")
        if len(future) == steps and np.isfinite(future).all() and np.array_equal(future_times, expected):
            output[i] = np.max(future) if peak else future[-1]
    return pd.Series(output, index=series.index)


def supervised_table(weather: pd.DataFrame, air: pd.DataFrame, horizon_hours: int, *, peak: bool) -> pd.DataFrame:
    frame = build_feature_frame(weather, air)
    if frame.empty or "us_aqi" not in frame:
        return pd.DataFrame(columns=["time", *FEATURES, "target"])
    frame["target"] = _future_values(frame["us_aqi"], frame["time"], horizon_hours, peak)
    historical = frame.loc[~frame["is_forecast"].fillna(False)].copy()
    return historical.dropna(subset=[*FEATURES, "target"]).reset_index(drop=True)


def chronological_split(
    samples: pd.DataFrame,
    horizon_hours: int,
    test_fraction: float = 0.2,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split by time and purge at least H hours so future labels cannot cross the boundary."""
    if samples.empty or not 0 < test_fraction < 1:
        return samples.iloc[0:0].copy(), samples.iloc[0:0].copy()
    ordered = samples.sort_values("time").reset_index(drop=True)
    unique_times = pd.Index(ordered["time"].drop_duplicates())
    split_at = min(max(1, int(len(unique_times) * (1 - test_fraction))), len(unique_times) - 1)
    if split_at >= len(unique_times):
        return ordered.iloc[0:0].copy(), ordered.iloc[0:0].copy()
    test_start = pd.Timestamp(unique_times[split_at])
    train = ordered.loc[ordered.time <= test_start - pd.Timedelta(horizon_hours, unit="h")].copy()
    test = ordered.loc[ordered.time >= test_start].copy()
    return train.reset_index(drop=True), test.reset_index(drop=True)


def _three_way_time_split(samples: pd.DataFrame, horizon_hours: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ordered = samples.sort_values("time").reset_index(drop=True)
    times = pd.Index(ordered.time.drop_duplicates())
    if len(times) < 5:
        empty = ordered.iloc[0:0].copy()
        return empty, empty.copy(), empty.copy()
    cal_start = pd.Timestamp(times[min(max(1, int(len(times) * 0.6)), len(times) - 2)])
    test_start = pd.Timestamp(times[min(max(2, int(len(times) * 0.8)), len(times) - 1)])
    train = ordered.loc[ordered.time <= cal_start - pd.Timedelta(horizon_hours, unit="h")]
    calibration = ordered.loc[(ordered.time >= cal_start) & (ordered.time <= test_start - pd.Timedelta(horizon_hours, unit="h"))]
    test = ordered.loc[ordered.time >= test_start]
    return train.reset_index(drop=True), calibration.reset_index(drop=True), test.reset_index(drop=True)


def _new_classifier() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=100, learning_rate=0.06, max_leaf_nodes=15,
        l2_regularization=2.0, random_state=23,
    )


def _new_regressor() -> HistGradientBoostingRegressor:
    return HistGradientBoostingRegressor(
        max_iter=100, learning_rate=0.06, max_leaf_nodes=15,
        l2_regularization=2.0, random_state=23,
    )


def _safe_metrics(labels: np.ndarray, probabilities: np.ndarray) -> dict[str, float | int | None]:
    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    return {
        "n": int(len(labels)),
        "brier": float(brier_score_loss(labels, probabilities)) if len(labels) else None,
        "roc_auc": float(roc_auc_score(labels, probabilities)) if len(np.unique(labels)) == 2 else None,
        "pr_auc": float(average_precision_score(labels, probabilities)) if len(labels) and labels.sum() else None,
    }


def _fit_classifier(dataset: pd.DataFrame, horizon: int, threshold: int) -> dict[str, Any]:
    samples = dataset.copy()
    samples["target"] = (samples.target > threshold).astype(int)
    train, calibration, test = _three_way_time_split(samples, horizon)
    unavailable = {"status": "insufficient", "horizon": horizon, "threshold": threshold, "train_n": len(train), "calibration_n": len(calibration), "test_n": len(test)}
    if len(train) < 100 or len(calibration) < 30 or len(test) < 30 or train.target.nunique() < 2 or calibration.target.nunique() < 2:
        unavailable["reason"] = "Chưa có đủ chuỗi lịch sử liên tục và đủ cả hai trạng thái để huấn luyện, hiệu chỉnh và kiểm tra theo thời gian."
        return unavailable
    model = _new_classifier()
    model.fit(train[list(FEATURES)], train.target, sample_weight=compute_sample_weight("balanced", train.target))
    calibration_raw = model.predict_proba(calibration[list(FEATURES)])[:, 1]
    calibrator = LogisticRegression(C=1.0, solver="lbfgs", random_state=23)
    calibrator.fit(calibration_raw.reshape(-1, 1), calibration.target)
    test_raw = model.predict_proba(test[list(FEATURES)])[:, 1]
    probabilities = calibrator.predict_proba(test_raw.reshape(-1, 1))[:, 1]
    model_metrics = _safe_metrics(test.target.to_numpy(), probabilities)
    prevalence = float(train.target.mean())
    climatology = np.full(len(test), prevalence)
    current_baseline = (test["us_aqi_lag_1h"].to_numpy() > threshold).astype(float)
    # Alert threshold follows an explicit planner cost assumption: a missed
    # unhealthy period costs 3 units, a false alert costs 1 (1 / (3 + 1)).
    alert_threshold = 0.25
    alarm = probabilities >= alert_threshold
    false_negative = int(((test.target.to_numpy() == 1) & ~alarm).sum())
    false_positive = int(((test.target.to_numpy() == 0) & alarm).sum())
    try:
        observed, predicted = calibration_curve(test.target, probabilities, n_bins=min(8, max(3, len(test) // 15)), strategy="quantile")
        calibration_points = [(float(p), float(o)) for p, o in zip(predicted, observed)]
    except ValueError:
        calibration_points = []
    return {
        "status": "ready", "horizon": horizon, "threshold": threshold,
        "model": model, "calibrator": calibrator,
        "train_n": len(train), "calibration_n": len(calibration), "test_n": len(test),
        "metrics": model_metrics,
        "climatology": _safe_metrics(test.target.to_numpy(), climatology),
        "current_over_threshold": _safe_metrics(test.target.to_numpy(), current_baseline),
        "prevalence": prevalence, "alert_threshold": alert_threshold,
        "false_negative": false_negative, "false_positive": false_positive,
        "calibration_points": calibration_points,
        "test_probabilities": probabilities.tolist(),
        "test_labels": test.target.astype(int).tolist(),
    }


def _fit_regressor(dataset: pd.DataFrame, horizon: int, feature_set: tuple[str, ...] = FEATURES) -> dict[str, Any]:
    train, test = chronological_split(dataset, horizon, test_fraction=0.2)
    result: dict[str, Any] = {"status": "insufficient", "horizon": horizon, "train_n": len(train), "test_n": len(test)}
    if len(train) < 100 or len(test) < 25:
        result["reason"] = "Chuỗi giờ hợp lệ chưa đủ để kiểm tra dự báo ngoài mẫu."
        return result
    model = _new_regressor()
    model.fit(train[list(feature_set)], train.target)
    predicted = model.predict(test[list(feature_set)])
    persistence = test["us_aqi_lag_1h"].to_numpy(dtype=float)
    result.update({
        "status": "ready", "model": model, "features": feature_set,
        "mae": float(mean_absolute_error(test.target, predicted)),
        "persistence_mae": float(mean_absolute_error(test.target, persistence)),
        "test_n": len(test), "train_n": len(train),
        "test_times": test.time.astype(str).tolist(),
        "test_actual": test.target.astype(float).tolist(),
        "test_predicted": np.asarray(predicted, dtype=float).tolist(),
        "persistence_predicted": persistence.tolist(),
        "X_reference": train[list(feature_set)].copy(),
        "X_evaluation": test[list(feature_set)].copy(),
        "y_evaluation": test.target.astype(float).to_numpy(),
    })
    return result


def _feature_value_text(name: str, value: float) -> str:
    if name == "temperature_2m":
        return f"{value:.1f}°C"
    if name in ("wind_speed_10m", "wind_mean_6h"):
        return f"{value:.1f} km/h"
    if name == "relative_humidity_2m":
        return f"{value:.0f}%"
    if name == "uv_index":
        return f"UV {value:.1f}"
    if name in ("us_aqi_lag_1h", "us_aqi_lag_3h", "us_aqi_lag_6h", "us_aqi_mean_6h", "us_aqi_mean_24h"):
        return f"AQI {value:.0f}"
    if name in ("pm25_lag_1h", "pm25_lag_6h", "pm25_mean_6h"):
        return f"PM₂.₅ {value:.1f} µg/m³"
    if name in ("hours_since_rain",):
        return f"{value:.0f} giờ"
    if name == "precipitation_sum_24h":
        return f"{value:.1f} mm/24 giờ"
    if name == "precipitation":
        return f"{value:.1f} mm trong giờ"
    if name == "pressure_change_3h":
        return f"{value:+.1f} hPa/3 giờ"
    if name == "surface_pressure":
        return f"{value:.0f} hPa"
    return f"{value:.2f}"


def generate_explanations(contributions: dict[str, float], current: pd.Series) -> list[str]:
    """Turn measured model contributions into short, cautious Vietnamese text."""
    ordered = sorted(
        ((name, float(value)) for name, value in contributions.items() if name in current and pd.notna(current[name]) and abs(float(value)) >= 0.5),
        key=lambda pair: abs(pair[1]), reverse=True,
    )[:3]
    sentences = []
    for name, effect in ordered:
        direction = "kéo dự báo lên" if effect > 0 else "kéo dự báo xuống"
        label = FEATURE_LABELS.get(name, name)
        value = _feature_value_text(name, float(current[name]))
        sentences.append(f"Trong dự báo 6 giờ, {label} hiện ở mức {value}; theo mô hình, mức này {direction} khoảng {abs(effect):.0f} điểm so với mức tham chiếu.")
    if not sentences:
        return ["Các yếu tố hiện tại không làm thay đổi đáng kể mức dự báo so với mẫu huấn luyện; chưa có yếu tố trội để giải thích."]
    return sentences


def _explain_regressor(
    model: Any,
    reference: pd.DataFrame,
    current: pd.Series,
    names: tuple[str, ...],
    evaluation: pd.DataFrame,
    evaluation_target: np.ndarray,
) -> dict[str, Any]:
    row = current[list(names)].astype(float).to_frame().T
    method = "SHAP TreeExplainer"
    values: dict[str, float] = {}
    try:
        import shap

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(row)
        array = np.asarray(shap_values, dtype=float).reshape(-1)
        if len(array) != len(names) or not np.isfinite(array).all():
            raise ValueError("SHAP did not return one finite value per feature")
        values = dict(zip(names, array.tolist()))
    except Exception:
        # HistGradientBoosting is not supported by every SHAP release. The
        # fallback ranks held-out permutation importance, then measures the
        # local change when each feature is replaced by its training median.
        method = "Permutation importance + thay biến bằng trung vị huấn luyện"
        try:
            sample = evaluation[list(names)].tail(min(160, len(evaluation)))
            if len(sample) >= 20:
                target = np.asarray(evaluation_target)[-len(sample):]
                importance = permutation_importance(model, sample, target, n_repeats=3, random_state=23, scoring="neg_mean_absolute_error")
                ranked = np.argsort(importance.importances_mean)[::-1][:8]
            else:
                ranked = np.arange(len(names))
            baseline = float(model.predict(row)[0])
            medians = reference[list(names)].median()
            for index in ranked:
                name = names[int(index)]
                changed = row.copy()
                changed.loc[:, name] = medians[name]
                values[name] = baseline - float(model.predict(changed)[0])
        except Exception:
            values = {}
    return {"method": method, "contributions": values, "sentences": generate_explanations(values, current)}


@st.cache_resource(show_spinner=False)
def train_city_suite(city: str, weather_hourly: pd.DataFrame, air_hourly: pd.DataFrame) -> dict[str, Any]:
    """Train/evaluate once per city and exact API-history version per process."""
    features = build_feature_frame(weather_hourly, air_hourly)
    historical = features.loc[~features.is_forecast.fillna(False)] if not features.empty else features
    latest_rows = historical.dropna(subset=list(FEATURES)) if not historical.empty else historical
    current = latest_rows.iloc[-1] if not latest_rows.empty else None
    suite: dict[str, Any] = {
        "city": city, "historical_hours": int(len(historical)),
        "latest": current, "classification": {100: {}, 150: {}}, "regression": {},
        "explanation": None, "status": "ready" if current is not None else "unavailable",
    }
    for horizon in HORIZONS:
        peak_data = supervised_table(weather_hourly, air_hourly, horizon, peak=True)
        for threshold in (100, 150):
            peak_data = peak_data.copy()
            peak_data["target"] = peak_data.target.astype(float)
            suite["classification"][threshold][horizon] = _fit_classifier(peak_data, horizon, threshold)
    regression_tables = {h: supervised_table(weather_hourly, air_hourly, h, peak=False) for h in REGRESSION_HORIZONS}
    for horizon, dataset in regression_tables.items():
        suite["regression"][horizon] = _fit_regressor(dataset, horizon)
    six_hour_data = regression_tables.get(6, pd.DataFrame())
    suite["ablation"] = _fit_regressor(six_hour_data, 6, AQI_LAG_FEATURES)
    main_regression = suite["regression"].get(6, {})
    if current is not None and main_regression.get("status") == "ready":
        suite["explanation"] = _explain_regressor(
            main_regression["model"], main_regression["X_reference"], current,
            main_regression["features"], main_regression["X_evaluation"],
            main_regression["y_evaluation"],
        )
    else:
        suite["explanation"] = {"method": "Chưa thể giải thích", "contributions": {}, "sentences": ["Chuỗi AQI và thời tiết hiện có chưa đủ để kiểm định mô hình giải thích."]}
    return suite


def predict_exceedance(model_result: dict[str, Any], latest: pd.Series | None) -> float | None:
    if not isinstance(model_result, dict) or latest is None or model_result.get("status") != "ready":
        return None
    try:
        values = pd.to_numeric(latest.reindex(FEATURES), errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            return None
        features = pd.DataFrame([values.to_numpy(dtype=float)], columns=FEATURES)
        model = model_result["model"]
        raw_probabilities = np.asarray(model.predict_proba(features), dtype=float)
        model_classes = np.asarray(model.classes_)
        positive_index = np.flatnonzero(model_classes == 1)
        if raw_probabilities.ndim != 2 or raw_probabilities.shape[0] != 1 or len(positive_index) != 1:
            return None
        raw = float(raw_probabilities[0, int(positive_index[0])])
        calibrator = model_result["calibrator"]
        calibrated = np.asarray(calibrator.predict_proba(np.array([[raw]], dtype=float)), dtype=float)
        calibrated_classes = np.asarray(calibrator.classes_)
        calibrated_positive = np.flatnonzero(calibrated_classes == 1)
        if calibrated.ndim != 2 or calibrated.shape[0] != 1 or len(calibrated_positive) != 1:
            return None
        return float(np.clip(calibrated[0, int(calibrated_positive[0])], 0.0, 1.0))
    except (AttributeError, ValueError, KeyError, TypeError, IndexError):
        return None


def predict_next_aqi(model_result: dict[str, Any], row: pd.Series) -> float | None:
    if model_result.get("status") != "ready":
        return None
    try:
        prediction = float(model_result["model"].predict(row[list(model_result["features"])].to_frame().T)[0])
        return float(np.clip(prediction, 0, 500))
    except (ValueError, KeyError, TypeError, IndexError):
        return None


def planner_forecast(
    weather_hourly: pd.DataFrame,
    air_hourly: pd.DataFrame,
    one_hour_model: dict[str, Any] | None,
    hours: int = 48,
) -> pd.DataFrame:
    """Use API AQI forecast where present, and ML only to fill absent forecast AQI hours."""
    if weather_hourly.empty:
        return pd.DataFrame()
    weather = weather_hourly.copy()
    weather["time"] = pd.to_datetime(weather["time"], errors="coerce")
    weather = weather.dropna(subset=["time"]).drop_duplicates("time", keep="last")
    now = pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").tz_localize(None)
    future_weather = weather.loc[(weather.time > now) & (weather.time <= now + pd.Timedelta(hours=hours))].copy()
    if future_weather.empty:
        return pd.DataFrame()

    air_work = air_hourly.copy() if air_hourly is not None else pd.DataFrame()
    if not air_work.empty:
        air_work["time"] = pd.to_datetime(air_work["time"], errors="coerce")
        air_work = air_work.dropna(subset=["time"]).drop_duplicates("time", keep="last")
    ml_predictions: dict[pd.Timestamp, float] = {}
    model_ready = bool(one_hour_model and one_hour_model.get("status") == "ready")
    for target_time in future_weather.time.sort_values():
        existing = air_work.loc[air_work.time.eq(target_time)] if not air_work.empty else pd.DataFrame()
        api_value = pd.to_numeric(existing["us_aqi"], errors="coerce").dropna() if "us_aqi" in existing else pd.Series(dtype=float)
        if len(api_value) or not model_ready:
            continue
        combined_features = build_feature_frame(weather, air_work)
        previous_time = target_time - pd.Timedelta(hours=1)
        prior = combined_features.loc[combined_features.time.eq(previous_time)]
        if prior.empty:
            continue
        row = prior.iloc[-1]
        prediction = predict_next_aqi(one_hour_model, row)
        if prediction is None:
            continue
        ml_predictions[target_time] = prediction
        append = {
            "time": target_time,
            "us_aqi": prediction,
            "us_aqi_pm2_5": np.nan,
            "pm2_5": np.nan,
            "is_forecast": True,
        }
        air_work = pd.concat([air_work, pd.DataFrame([append])], ignore_index=True)
        air_work = air_work.drop_duplicates("time", keep="last")

    selected_columns = [name for name in ("time", "us_aqi", "us_aqi_pm2_5", "pm2_5") if name in air_work]
    result = future_weather.merge(air_work[selected_columns], on="time", how="left") if selected_columns else future_weather.copy()
    result["aqi_source"] = np.where(result.get("us_aqi", pd.Series(index=result.index, dtype=float)).notna(), "Dự báo Open-Meteo", "")
    if "us_aqi" not in result:
        result["us_aqi"] = np.nan
    if "us_aqi_pm2_5" not in result:
        result["us_aqi_pm2_5"] = np.nan
    for index, row in result.iterrows():
        timestamp = pd.Timestamp(row.time)
        if pd.isna(row.us_aqi) and timestamp in ml_predictions:
            result.loc[index, "us_aqi"] = ml_predictions[timestamp]
            result.loc[index, "aqi_source"] = "Dự báo ML của project"
    return result.sort_values("time").reset_index(drop=True)

