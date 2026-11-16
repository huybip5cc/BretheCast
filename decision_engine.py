"""Dự báo AQI bằng hai mô hình tuyến tính, đủ ngắn để giải thích trước lớp.

* Logistic Regression  -> xác suất "AQI có vượt ngưỡng trong H giờ tới không" (phân loại).
* Ridge Regression     -> AQI sau H giờ, học *phần trăm thay đổi* so với AQI hiện tại (hồi quy).

Cả hai đều là "cộng các yếu tố có trọng số", nên giải thích được chính xác từng yếu tố đóng góp bao nhiêu.
Kiểm tra công bằng: chia theo thời gian (không xáo trộn), chừa khoảng H giờ, và luôn so với baseline.
"""

from __future__ import annotations

import unicodedata
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st
from sklearn.calibration import calibration_curve
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, mean_absolute_error, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HORIZONS = (6, 12, 24)               # dự báo xác suất sau 6/12/24 giờ
REGRESSION_HORIZONS = (1, 6, 12, 24)  # dự báo giá trị AQI sau 1/6/12/24 giờ
ALERT = 0.25                          # báo động khi xác suất >= 25% (bỏ sót tốn gấp 3 lần báo nhầm: 1/(1+3))

# Ngưỡng US AQI theo thành phố. Hà Nội nền ô nhiễm cao: ngưỡng 100 bị vượt gần như mọi lúc nên dùng 150 và 200.
DEFAULT_THRESHOLDS = (100, 150)
CITY_THRESHOLDS = {"Hà Nội": (100, 150)}

FEATURE_LABELS = {
    "temperature_2m": "Nhiệt độ", "relative_humidity_2m": "Độ ẩm", "wind_mean_6h": "Gió trung bình 6 giờ",
    "precipitation_sum_24h": "Tổng mưa 24 giờ", "pressure_change_3h": "Thay đổi áp suất 3 giờ",
    "hour_sin": "Giờ trong ngày", "hour_cos": "Giờ trong ngày",
    "us_aqi_now": "AQI hiện tại", "us_aqi_change_1h": "Xu hướng AQI 1 giờ", "us_aqi_change_3h": "Xu hướng AQI 3 giờ",
    "us_aqi_mean_24h": "AQI trung bình 24 giờ", "us_aqi_max_24h": "AQI cao nhất 24 giờ", "pm25_now": "PM₂.₅ hiện tại",
}
FEATURES = tuple(FEATURE_LABELS)
# Hồi quy dùng đặc trưng TƯƠNG ĐỐI (phần trăm), không dùng mức AQI tuyệt đối: mô hình học "AQI đang tăng/giảm bao nhiêu %"
# chứ không học thuộc "mức nền" của giai đoạn học, nên không sai khi mức nền của giai đoạn thi khác đi.
REG_LABELS = {
    "us_aqi_mom1": "Xu hướng AQI 1 giờ", "us_aqi_mom3": "Xu hướng AQI 3 giờ",
    "us_aqi_rel_mean24": "AQI so với trung bình 24 giờ", "us_aqi_rel_max24": "AQI so với mức cao nhất 24 giờ",
    "us_aqi_yday": "Thay đổi AQI cùng khung giờ hôm qua", "hour_sin": "Giờ trong ngày", "hour_cos": "Giờ trong ngày",
}
REG_BASE = ("us_aqi_mom1", "us_aqi_mom3", "us_aqi_rel_mean24", "us_aqi_rel_max24", "hour_sin", "hour_cos")
AQI_ONLY = REG_BASE[:4]               # cho mô hình đối chứng (ablation): chỉ dùng AQI trễ, bỏ chu kỳ ngày
RIDGE_ALPHA = 300                     # dùng khi validation không đủ để chọn alpha
RIDGE_ALPHAS = (1000, 300, 100)        # chỉ thử vài mức regularization dễ giải thích


def regression_features(horizon: int) -> tuple[str, ...]:
    """6 đặc trưng chung + "AQI cùng khung giờ hôm qua đã thay đổi bao nhiêu %" (đã biết tại thời điểm dự báo)."""
    return REG_BASE + (f"us_aqi_yday_{horizon}h",)
WEATHER_COLS = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m", "precipitation", "surface_pressure"]
AIR_COLS = ["us_aqi", "pm2_5"]


def thresholds_for_city(city: str) -> tuple[int, int]:
    key = lambda name: unicodedata.normalize("NFC", str(name)).strip().casefold()
    return tuple({key(k): v for k, v in CITY_THRESHOLDS.items()}.get(key(city), DEFAULT_THRESHOLDS))


# ------------------------------------------------------------------ 1. Dữ liệu -> bảng (mỗi dòng = một giờ)

def _hourly_grid(weather: pd.DataFrame, air: pd.DataFrame) -> pd.DataFrame:
    """Ghép thời tiết và AQI theo từng giờ; giờ thiếu vẫn là NaN (không bịa số)."""
    parts = []
    for frame, columns in ((weather, WEATHER_COLS), (air, AIR_COLS)):
        if frame is not None and not frame.empty:
            f = frame.assign(time=pd.to_datetime(frame["time"], errors="coerce")).dropna(subset=["time"])
            f = f.drop_duplicates("time", keep="last").set_index("time")
            parts.append(f.reindex(columns=columns).apply(pd.to_numeric, errors="coerce"))
    if not parts:
        return pd.DataFrame()
    grid = pd.concat(parts, axis=1).reindex(columns=WEATHER_COLS + AIR_COLS).sort_index()
    grid = grid.reindex(pd.date_range(grid.index.min().floor("h"), grid.index.max().ceil("h"), freq="h", name="time"))
    grid["is_forecast"] = grid.index > pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").tz_localize(None)
    return grid


def build_feature_frame(weather: pd.DataFrame, air: pd.DataFrame) -> pd.DataFrame:
    """Đặc trưng chỉ dùng thông tin của giờ hiện tại và quá khứ (không nhìn trộm tương lai)."""
    g = _hourly_grid(weather, air)
    if g.empty:
        return pd.DataFrame(columns=["time", *FEATURES, "is_forecast"])
    aqi, hour = g["us_aqi"], g.index.hour
    logaqi = np.log(aqi.clip(lower=1))                                  # AQI dạng log: hiệu của log = phần trăm thay đổi
    mean24, max24 = aqi.rolling(24, min_periods=16).mean(), aqi.rolling(24, min_periods=16).max()
    f = pd.DataFrame({
        "temperature_2m": g["temperature_2m"], "relative_humidity_2m": g["relative_humidity_2m"],
        "wind_mean_6h": g["wind_speed_10m"].rolling(6, min_periods=4).mean(),
        "precipitation_sum_24h": g["precipitation"].rolling(24, min_periods=18).sum(),
        "pressure_change_3h": g["surface_pressure"].diff(3),
        "hour_sin": np.sin(2 * np.pi * hour / 24), "hour_cos": np.cos(2 * np.pi * hour / 24),  # 23h và 0h gần nhau
        "us_aqi_now": aqi, "us_aqi_change_1h": aqi.diff(1), "us_aqi_change_3h": aqi.diff(3),
        "us_aqi_mean_24h": mean24, "us_aqi_max_24h": max24,
        "pm25_now": g["pm2_5"], "is_forecast": g["is_forecast"],
        # --- đặc trưng tương đối cho hồi quy (đơn vị: %) ---
        "us_aqi_mom1": 100 * (logaqi - logaqi.shift(1)), "us_aqi_mom3": 100 * (logaqi - logaqi.shift(3)),
        "us_aqi_rel_mean24": 100 * (logaqi - np.log(mean24.clip(lower=1))),
        "us_aqi_rel_max24": 100 * (logaqi - np.log(max24.clip(lower=1))),
        **{f"us_aqi_yday_{h}h": 100 * (logaqi.shift(24 - h) - logaqi.shift(24)) for h in REGRESSION_HORIZONS},
    }, index=g.index)
    return f.reset_index()


def supervised_table(weather: pd.DataFrame, air: pd.DataFrame, horizon: int, *, peak: bool) -> pd.DataFrame:
    """Build one supervised table for the requested forecast horizon."""
    return _supervised_feature_table(build_feature_frame(weather, air), horizon, peak)


def _supervised_feature_table(features: pd.DataFrame, horizon: int, peak: bool) -> pd.DataFrame:
    """Add a future AQI label to a prebuilt feature frame."""
    if features.empty:
        return features.assign(target=np.nan)
    f = features.copy()
    seen = f["us_aqi_now"].where(~f["is_forecast"])
    f["target"] = seen.rolling(horizon).max().shift(-horizon) if peak else seen.shift(-horizon)
    return f.loc[~f["is_forecast"]].dropna(subset=[*FEATURES, "target"]).reset_index(drop=True)


def _split(data: pd.DataFrame, horizon: int, test_fraction: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chia theo thời gian: phần cũ để học, 20% mới nhất để thi, chừa H giờ ở giữa để đáp án không bị lộ."""
    times = data["time"].drop_duplicates().sort_values().reset_index(drop=True)
    start = times.iloc[min(int(len(times) * (1 - test_fraction)), len(times) - 1)] if len(times) else pd.NaT
    return data[data.time <= start - pd.Timedelta(hours=horizon)], data[data.time >= start]


# ------------------------------------------------------------------ 2. Phân loại: Logistic Regression

def _scores(y: np.ndarray, p: np.ndarray) -> dict[str, float | int | None]:
    both = len(np.unique(y)) == 2
    return {"n": int(len(y)), "brier": float(brier_score_loss(y, p)),
            "roc_auc": float(roc_auc_score(y, p)) if both else None,
            "pr_auc": float(average_precision_score(y, p)) if y.sum() else None}


def _fit_classifier(data: pd.DataFrame, horizon: int, threshold: int) -> dict[str, Any]:
    data = data.assign(target=(data.target > threshold).astype(int))   # nhãn 1 = có vượt ngưỡng
    train, test = _split(data, horizon)
    result: dict[str, Any] = {"status": "insufficient", "horizon": horizon, "threshold": threshold,
                              "train_n": len(train), "test_n": len(test)}
    if len(train) < 100 or len(test) < 30 or train.target.value_counts().reindex([0, 1], fill_value=0).min() < 8:
        result["reason"] = "Chưa đủ giờ liên tục, hoặc ngưỡng này quá hiếm/quá phổ biến để học và kiểm tra theo thời gian."
        return result
    columns = list(FEATURES)
    make = lambda: make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=1000))
    p = make().fit(train[columns], train.target).predict_proba(test[columns])[:, 1]   # thi trên 20% chưa từng thấy
    y = test.target.to_numpy()
    try:
        observed, predicted = calibration_curve(y, p, n_bins=min(8, max(3, len(test) // 15)), strategy="quantile")
        points = [(float(a), float(b)) for a, b in zip(predicted, observed)]
    except ValueError:
        points = []
    base = float(train.target.mean())
    result.update(
        status="ready", features=columns, model=make().fit(data[columns], data.target),   # mô hình dùng thật: học lại trên toàn bộ
        metrics=_scores(y, p),
        climatology=_scores(y, np.full(len(y), base)),                                    # baseline 1: luôn đoán tần suất chung
        current_over_threshold=_scores(y, (test.us_aqi_now > threshold).astype(float).to_numpy()),  # baseline 2: "đang vượt thì sẽ vượt"
        prevalence=base, alert_threshold=ALERT,
        false_negative=int(((y == 1) & (p < ALERT)).sum()), false_positive=int(((y == 0) & (p >= ALERT)).sum()),
        calibration_points=points, test_probabilities=p.tolist(), test_labels=y.tolist(),
    )
    return result


def predict_exceedance(result: dict[str, Any], latest: pd.Series | None) -> float | None:
    """Xác suất (0-1) AQI vượt ngưỡng cho dòng dữ liệu mới nhất."""
    if latest is None or result.get("status") != "ready":
        return None
    row = pd.to_numeric(latest.reindex(result["features"]), errors="coerce")
    if row.isna().any():
        return None
    return float(result["model"].predict_proba(row.to_frame().T)[0, 1])


def explain_probability(result: dict[str, Any], latest: pd.Series) -> dict[str, Any]:
    """Phân rã chính xác: logit = hệ số chặn + tổng(trọng số × giá trị chuẩn hóa); xác suất = sigmoid(logit)."""
    scaler, logistic = result["model"][0], result["model"][-1]
    names = result["features"]
    z = scaler.transform(pd.to_numeric(latest.reindex(names)).to_frame().T)[0]
    rows = [{"feature": n, "value": float(latest[n]), "z": float(zi), "weight": float(w), "contribution": float(w * zi)}
            for n, zi, w in zip(names, z, logistic.coef_[0])]
    logit = float(logistic.intercept_[0] + sum(r["contribution"] for r in rows))
    return {"intercept": float(logistic.intercept_[0]), "rows": rows, "logit": logit, "probability": 1 / (1 + np.exp(-logit))}


# ------------------------------------------------------------------ 3. Hồi quy: Ridge học phần trăm thay đổi

def _ridge(alpha: float = RIDGE_ALPHA):
    return make_pipeline(StandardScaler(), Ridge(alpha=alpha, fit_intercept=False))


def _pct_change(d: pd.DataFrame) -> pd.Series:
    """Đáp án của hồi quy: AQI sau H giờ đã thay đổi bao nhiêu % so với AQI hiện tại."""
    return 100 * np.log(d.target.clip(lower=1) / d.us_aqi_now.clip(lower=1))


def _level(now: pd.Series, pct: np.ndarray, shrink: float) -> np.ndarray:
    """Đổi phần trăm thay đổi dự đoán về giá trị AQI; shrink (0..1) là mức mô hình được phép điều chỉnh baseline."""
    return np.clip(now.to_numpy() * np.exp(shrink * np.asarray(pct) / 100), 0, 500)


def _rolling_validation_folds(data: pd.DataFrame, horizon: int) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    """Tạo bốn cửa sổ kiểm tra tiến về phía trước; nhãn tập học không chạm vào tập validation."""
    times = data["time"].drop_duplicates().sort_values().reset_index(drop=True)
    folds = []
    for start_fraction in (0.50, 0.62, 0.74, 0.86):
        start_pos = min(int(len(times) * start_fraction), len(times) - 1)
        end_pos = min(int(len(times) * (start_fraction + 0.10)), len(times) - 1)
        start, end = times.iloc[start_pos], times.iloc[end_pos]
        fit = data.loc[data.time <= start - pd.Timedelta(hours=horizon)]
        valid = data.loc[data.time.between(start, end)]
        if len(fit) >= 80 and len(valid) >= 20:
            folds.append((fit, valid))
    return folds


def _fit_regressor(data: pd.DataFrame, horizon: int, features: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Chọn Ridge bằng validation cuốn chiếu, rồi chặn nếu thua ở đoạn dữ liệu gần nhất."""
    columns = list(features or regression_features(horizon))
    if any(c not in data.columns for c in columns):          # chưa có dữ liệu nào để tạo đặc trưng
        return {"status": "insufficient", "horizon": horizon, "train_n": 0, "test_n": 0, "reason": "Chưa có dữ liệu."}
    data = data.dropna(subset=columns)
    train, test = _split(data, horizon)
    result: dict[str, Any] = {"status": "insufficient", "horizon": horizon, "train_n": len(train), "test_n": len(test)}
    if len(train) < 100 or len(test) < 25:
        result["reason"] = "Chuỗi giờ hợp lệ chưa đủ để kiểm tra dự báo ngoài mẫu."
        return result
    # Chọn Ridge, alpha và mức co chỉ từ các cửa sổ cũ hơn; không dùng tập kiểm tra cuối.
    folds = _rolling_validation_folds(train, horizon)
    candidates = []
    for alpha in RIDGE_ALPHAS:
        for shrink in (0, 0.25, 0.5, 0.75, 1):
            fold_mae, fold_baseline = [], []
            for fit, valid in folds:
                model = _ridge(alpha).fit(fit[columns], _pct_change(fit))
                pct = model.predict(valid[columns])
                fold_mae.append(mean_absolute_error(valid.target, _level(valid.us_aqi_now, pct, shrink)))
                fold_baseline.append(mean_absolute_error(valid.target, valid.us_aqi_now))
            if fold_mae:
                candidates.append((float(np.mean(fold_mae)), -sum(a < b for a, b in zip(fold_mae, fold_baseline)), -alpha, shrink, alpha, fold_mae, fold_baseline))

    if candidates and len(folds) >= 3:
        validation_mae, _wins_sort, _alpha_sort, candidate_shrink, alpha, fold_mae, fold_baseline = min(candidates)
        baseline_validation_mae = float(np.mean(fold_baseline))
        fold_lifts = [(b - a) / max(b, 1e-9) for a, b in zip(fold_mae, fold_baseline)]
        validation_wins = sum(lift > 0 for lift in fold_lifts)
        validation_lift = (baseline_validation_mae - validation_mae) / max(baseline_validation_mae, 1e-9)
    else:
        candidate_shrink, alpha = 0.0, RIDGE_ALPHA
        validation_mae = baseline_validation_mae = validation_lift = float("nan")
        validation_wins, fold_lifts = 0, []
    validation_selected = (
        len(folds) >= 3 and candidate_shrink > 0
        and validation_wins == len(folds) and validation_lift >= 0.01
    )

    # Cổng vận hành: không triển khai Ridge nếu nó thua baseline trên 20% dữ liệu mới nhất.
    test_model = _ridge(alpha).fit(train[columns], _pct_change(train))
    pct_test = test_model.predict(test[columns])
    ridge_test_mae = float(mean_absolute_error(test.target, _level(test.us_aqi_now, pct_test, candidate_shrink)))
    baseline = float(mean_absolute_error(test.target, test.us_aqi_now))
    selected = "ridge" if validation_selected and ridge_test_mae < baseline else "persistence"
    shrink = candidate_shrink if selected == "ridge" else 0.0
    mae = ridge_test_mae if selected == "ridge" else baseline
    result.update(
        status="ready", features=tuple(columns), shrink=shrink, alpha=alpha,
        mae=mae, candidate_mae=ridge_test_mae, persistence_mae=baseline,
        validation_selected=validation_selected, recent_gate_passed=ridge_test_mae < baseline,
        validation_mae=validation_mae, validation_persistence_mae=baseline_validation_mae,
        validation_lift=validation_lift, validation_fold_lifts=tuple(fold_lifts),
        validation_wins=validation_wins, validation_folds=len(folds),
        model=_ridge(alpha).fit(data[columns], _pct_change(data)),  # mô hình dùng thật: học lại trên toàn bộ
        selected=selected,
    )
    return result


def predict_next_aqi(result: dict[str, Any], row: pd.Series) -> float | None:
    """Trả AQI Ridge nếu qua validation và cổng gần nhất; nếu không, dùng baseline."""
    if result.get("status") != "ready" or result.get("selected") != "ridge":
        return None
    x = pd.to_numeric(row.reindex(result["features"]), errors="coerce")
    now = pd.to_numeric(pd.Series([row.get("us_aqi_now")]), errors="coerce")
    if now.isna().iloc[0]:
        return None                                   # không có AQI hiện tại thì không dự báo
    x = x.fillna(pd.Series(result["model"][0].mean_, index=x.index))  # đặc trưng phụ bị thiếu -> dùng giá trị trung bình lúc học
    return float(_level(now, result["model"].predict(x.to_frame().T), result["shrink"])[0])


# ------------------------------------------------------------------ 4. Giải thích bằng chữ

def _show(name: str, row: pd.Series) -> str:
    if name in ("hour_sin", "hour_cos"):
        return f"{pd.Timestamp(row['time']).hour} giờ" if "time" in row else "giờ hiện tại"
    if name in REG_LABELS or name.startswith("us_aqi_yday"):
        return f"{float(row[name]):+.1f}%"
    return f"{float(row[name]):.1f}"


def generate_explanations(contributions: dict[str, float], current: pd.Series) -> list[str]:
    top = sorted(((n, v) for n, v in contributions.items() if abs(v) >= 0.5), key=lambda kv: -abs(kv[1]))[:3]
    label = lambda n: REG_LABELS.get("us_aqi_yday" if n.startswith("us_aqi_yday") else n) or FEATURE_LABELS.get(n, n)
    lines = [f"Trong dự báo 6 giờ, {label(n)} hiện ở mức {_show(n, current)}; mức này "
             f"{'kéo dự báo lên' if v > 0 else 'kéo dự báo xuống'} khoảng {abs(v):.0f} điểm so với mức trung bình." for n, v in top]
    return lines or ["Các yếu tố hiện tại không làm thay đổi đáng kể dự báo so với mức trung bình."]


def _explain_regressor(result: dict[str, Any], latest: pd.Series) -> dict[str, Any]:
    """Ridge là tuyến tính nên đóng góp = hệ số × giá trị chuẩn hóa: chính xác, không phải xấp xỉ.
    Đổi từ % sang điểm AQI bằng cách nhân với AQI hiện tại (và hệ số co λ)."""
    names, model = result["features"], result["model"]
    z = model[0].transform(pd.to_numeric(latest.reindex(names)).to_frame().T)[0]
    scale = float(latest["us_aqi_now"]) * result["shrink"] / 100
    contributions = {n: float(w * zi * scale) for n, w, zi in zip(names, model[-1].coef_, z)}
    return {"method": "Hệ số Ridge × giá trị chuẩn hóa (đóng góp vào thay đổi AQI, tính bằng điểm)",
            "contributions": contributions, "sentences": generate_explanations(contributions, latest)}


# ------------------------------------------------------------------ 5. Ghép lại cho giao diện

@st.cache_resource(show_spinner=False)
def train_city_suite(city: str, weather_hourly: pd.DataFrame, air_hourly: pd.DataFrame) -> dict[str, Any]:
    thresholds = thresholds_for_city(city)
    features = build_feature_frame(weather_hourly, air_hourly)
    history = features.loc[~features.is_forecast.astype(bool)] if not features.empty else features
    complete = history.dropna(subset=list(FEATURES)) if not history.empty else history
    latest = complete.iloc[-1] if not complete.empty else None
    suite: dict[str, Any] = {"city": city, "historical_hours": int(len(history)), "latest": latest, "thresholds": thresholds,
                             "classification": {t: {} for t in thresholds}, "regression": {},
                             "status": "ready" if latest is not None else "unavailable"}
    classification_tables = {
        horizon: _supervised_feature_table(features, horizon, peak=True)
        for horizon in HORIZONS
    }
    for horizon, data in classification_tables.items():
        for threshold in thresholds:
            suite["classification"][threshold][horizon] = _fit_classifier(data, horizon, threshold)
    tables = {
        horizon: _supervised_feature_table(features, horizon, peak=False)
        for horizon in REGRESSION_HORIZONS
    }
    suite["regression"] = {h: _fit_regressor(t, h) for h, t in tables.items()}
    suite["ablation"] = _fit_regressor(tables[6], 6, AQI_ONLY)
    main = suite["regression"][6]
    if latest is not None and main["status"] == "ready" and main["selected"] == "ridge":
        suite["explanation"] = _explain_regressor(main, latest)
    else:
        suite["explanation"] = {"method": "Không áp dụng", "contributions": {}, "sentences": [
            "Mô hình chưa thắng cách giữ nguyên AQI hiện tại ở mốc 6 giờ nên không dùng để điều chỉnh dự báo."]}
    return suite


def planner_forecast(weather_hourly: pd.DataFrame, air_hourly: pd.DataFrame,
                     one_hour_model: dict[str, Any] | None, hours: int = 48) -> pd.DataFrame:
    """48 giờ tới: giờ nào Open-Meteo đã có AQI thì giữ nguyên; giờ thiếu mới nhờ mô hình 1 giờ lấp (có gắn nhãn)."""
    if weather_hourly.empty:
        return pd.DataFrame()
    weather = weather_hourly.assign(time=pd.to_datetime(weather_hourly["time"], errors="coerce")).dropna(subset=["time"])
    weather = weather.drop_duplicates("time", keep="last")
    now = pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").tz_localize(None)
    future = weather.loc[(weather.time > now) & (weather.time <= now + pd.Timedelta(hours=hours))].copy()
    if future.empty:
        return pd.DataFrame()
    air = air_hourly.copy() if air_hourly is not None else pd.DataFrame()
    if not air.empty:
        air = air.assign(time=pd.to_datetime(air["time"], errors="coerce")).dropna(subset=["time"]).drop_duplicates("time", keep="last")
    filled: set[pd.Timestamp] = set()
    if one_hour_model:
        for t in future.time.sort_values():
            has_api = not air.empty and pd.to_numeric(air.loc[air.time.eq(t), "us_aqi"], errors="coerce").notna().any()
            if has_api:
                continue
            start = t - pd.Timedelta(hours=26)
            recent_weather = weather.loc[(weather.time >= start) & (weather.time < t)]
            recent_air = air.loc[(air.time >= start) & (air.time < t)] if not air.empty else air
            frame = build_feature_frame(recent_weather, recent_air)
            previous = frame.loc[frame.time.eq(t - pd.Timedelta(hours=1))]
            value = predict_next_aqi(one_hour_model, previous.iloc[-1]) if not previous.empty else None
            if value is not None:
                filled.add(t)
                air = pd.concat([air, pd.DataFrame([{"time": t, "us_aqi": value, "us_aqi_pm2_5": np.nan, "pm2_5": np.nan, "is_forecast": True}])], ignore_index=True)
    columns = [c for c in ("time", "us_aqi", "us_aqi_pm2_5", "pm2_5") if c in air]
    result = future.merge(air[columns], on="time", how="left") if columns else future.copy()
    for name in ("us_aqi", "us_aqi_pm2_5"):
        if name not in result:
            result[name] = np.nan
    result["aqi_source"] = np.where(result.time.isin(list(filled)), "Dự báo ML của project",
                                    np.where(result["us_aqi"].notna(), "Dự báo Open-Meteo", ""))
    return result.sort_values("time").reset_index(drop=True)
