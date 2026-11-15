"""Dự báo AQI bằng hai mô hình tuyến tính, đủ ngắn để giải thích trước lớp.

* Logistic Regression  -> xác suất "AQI có vượt ngưỡng trong H giờ tới không" (phân loại).
* Ridge Regression     -> AQI sau H giờ, học phần *thay đổi* so với AQI hiện tại (hồi quy).

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
from sklearn.linear_model import LogisticRegression, RidgeCV
from sklearn.metrics import average_precision_score, brier_score_loss, mean_absolute_error, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HORIZONS = (6, 12, 24)               # dự báo xác suất sau 6/12/24 giờ
REGRESSION_HORIZONS = (1, 6, 12, 24)  # dự báo giá trị AQI sau 1/6/12/24 giờ
ALERT = 0.25                          # báo động khi xác suất >= 25% (bỏ sót tốn gấp 3 lần báo nhầm: 1/(1+3))

# Ngưỡng US AQI theo thành phố. Hà Nội nền ô nhiễm cao: ngưỡng 100 bị vượt gần như mọi lúc nên dùng 150 và 200.
DEFAULT_THRESHOLDS = (100, 150)
CITY_THRESHOLDS = {"Hà Nội": (120, 170)}

FEATURE_LABELS = {
    "temperature_2m": "Nhiệt độ", "relative_humidity_2m": "Độ ẩm", "wind_mean_6h": "Gió trung bình 6 giờ",
    "precipitation_sum_24h": "Tổng mưa 24 giờ", "pressure_change_3h": "Thay đổi áp suất 3 giờ",
    "hour_sin": "Giờ trong ngày", "hour_cos": "Giờ trong ngày",
    "us_aqi_now": "AQI hiện tại", "us_aqi_change_1h": "Xu hướng AQI 1 giờ", "us_aqi_change_3h": "Xu hướng AQI 3 giờ",
    "us_aqi_mean_24h": "AQI trung bình 24 giờ", "us_aqi_max_24h": "AQI cao nhất 24 giờ", "pm25_now": "PM₂.₅ hiện tại",
}
FEATURES = tuple(FEATURE_LABELS)
AQI_ONLY = ("us_aqi_now", "us_aqi_change_1h", "us_aqi_change_3h", "us_aqi_mean_24h", "us_aqi_max_24h")  # cho mô hình đối chứng (ablation)
WEATHER_COLS = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m", "precipitation", "surface_pressure"]
AIR_COLS = ["us_aqi", "pm2_5"]


def thresholds_for_city(city: str) -> tuple[int, int]:
    key = lambda name: unicodedata.normalize("NFC", str(name)).strip().casefold()
    return tuple({key(k): v for k, v in CITY_THRESHOLDS.items()}.get(key(city), DEFAULT_THRESHOLDS))


# ----------------- 1. Dữ liệu -> bảng (mỗi dòng = một giờ)

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
    f = pd.DataFrame({
        "temperature_2m": g["temperature_2m"], "relative_humidity_2m": g["relative_humidity_2m"],
        "wind_mean_6h": g["wind_speed_10m"].rolling(6, min_periods=4).mean(),
        "precipitation_sum_24h": g["precipitation"].rolling(24, min_periods=18).sum(),
        "pressure_change_3h": g["surface_pressure"].diff(3),
        "hour_sin": np.sin(2 * np.pi * hour / 24), "hour_cos": np.cos(2 * np.pi * hour / 24),  # 23h và 0h gần nhau
        "us_aqi_now": aqi, "us_aqi_change_1h": aqi.diff(1), "us_aqi_change_3h": aqi.diff(3),
        "us_aqi_mean_24h": aqi.rolling(24, min_periods=16).mean(),
        "us_aqi_max_24h": aqi.rolling(24, min_periods=16).max(),
        "pm25_now": g["pm2_5"], "is_forecast": g["is_forecast"],
    }, index=g.index)
    return f.reset_index()


def supervised_table(weather: pd.DataFrame, air: pd.DataFrame, horizon: int, *, peak: bool) -> pd.DataFrame:
    """Thêm cột target = đáp án ở tương lai, chỉ lấy từ các giờ ĐÃ xảy ra.
    peak=True : AQI cao nhất trong H giờ tới (để hỏi "có vượt ngưỡng không").  peak=False: AQI đúng sau H giờ."""
    f = build_feature_frame(weather, air)
    if f.empty:
        return f.assign(target=np.nan)
    seen = f["us_aqi_now"].where(~f["is_forecast"])
    f["target"] = seen.rolling(horizon).max().shift(-horizon) if peak else seen.shift(-horizon)
    return f.loc[~f["is_forecast"]].dropna(subset=[*FEATURES, "target"]).reset_index(drop=True)


def _split(data: pd.DataFrame, horizon: int, test_fraction: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chia theo thời gian: phần cũ để học, 20% mới nhất để thi, chừa H giờ ở giữa để đáp án không bị lộ."""
    times = data["time"].drop_duplicates().sort_values().reset_index(drop=True)
    start = times.iloc[min(int(len(times) * (1 - test_fraction)), len(times) - 1)] if len(times) else pd.NaT
    return data[data.time <= start - pd.Timedelta(hours=horizon)], data[data.time >= start]


# --------------------------- 2. Phân loại: Logistic Regression

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


# ---------------------- 3. Hồi quy: Ridge học phần thay đổi

def _ridge():
    return make_pipeline(StandardScaler(), RidgeCV(alphas=(1, 10, 100, 1000)))


def _fit_regressor(data: pd.DataFrame, horizon: int, features: tuple[str, ...] = FEATURES) -> dict[str, Any]:
    """AQI sau H giờ = AQI hiện tại + thay đổi do Ridge dự đoán."""
    train, test = _split(data, horizon)
    result: dict[str, Any] = {"status": "insufficient", "horizon": horizon, "train_n": len(train), "test_n": len(test)}
    if len(train) < 100 or len(test) < 25:
        result["reason"] = "Chuỗi giờ hợp lệ chưa đủ để kiểm tra dự báo ngoài mẫu."
        return result
    columns = list(features)
    change = lambda d: d.target - d.us_aqi_now
    predicted = test.us_aqi_now + _ridge().fit(train[columns], change(train)).predict(test[columns])
    mae = float(mean_absolute_error(test.target, predicted))
    baseline = float(mean_absolute_error(test.target, test.us_aqi_now))               # baseline: giữ nguyên AQI hiện tại
    result.update(status="ready", features=tuple(columns), model=_ridge().fit(data[columns], change(data)),
                  mae=mae, persistence_mae=baseline, selected="ridge" if mae < baseline else "persistence")
    return result


def predict_next_aqi(result: dict[str, Any], row: pd.Series) -> float | None:
    """AQI giờ kế tiếp; trả None nếu mô hình không thắng baseline (thà để trống còn hơn bịa số)."""
    if result.get("status") != "ready" or result.get("selected") != "ridge":
        return None
    x = pd.to_numeric(row.reindex(result["features"]), errors="coerce")
    if pd.isna(x["us_aqi_now"]):
        return None                                   # không có AQI hiện tại thì không dự báo
    x = x.fillna(pd.Series(result["model"][0].mean_, index=x.index))  # đặc trưng phụ bị thiếu -> dùng giá trị trung bình lúc học
    return float(np.clip(x["us_aqi_now"] + result["model"].predict(x.to_frame().T)[0], 0, 500))


# --------------------------- 4. Giải thích bằng chữ

def _show(name: str, row: pd.Series) -> str:
    if name in ("hour_sin", "hour_cos"):
        return f"{pd.Timestamp(row['time']).hour} giờ" if "time" in row else "giờ hiện tại"
    return f"{float(row[name]):.1f}"


def generate_explanations(contributions: dict[str, float], current: pd.Series) -> list[str]:
    top = sorted(((n, v) for n, v in contributions.items() if abs(v) >= 0.5), key=lambda kv: -abs(kv[1]))[:3]
    lines = [f"Trong dự báo 6 giờ, {FEATURE_LABELS.get(n, n)} hiện ở mức {_show(n, current)}; mức này "
             f"{'kéo dự báo lên' if v > 0 else 'kéo dự báo xuống'} khoảng {abs(v):.0f} điểm so với mức trung bình." for n, v in top]
    return lines or ["Các yếu tố hiện tại không làm thay đổi đáng kể dự báo so với mức trung bình."]


def _explain_regressor(model: Any, latest: pd.Series, features: tuple[str, ...]) -> dict[str, Any]:
    """Ridge là tuyến tính nên đóng góp = hệ số × giá trị chuẩn hóa: chính xác, không phải xấp xỉ."""
    z = model[0].transform(pd.to_numeric(latest.reindex(features)).to_frame().T)[0]
    contributions = {n: float(w * zi) for n, w, zi in zip(features, model[-1].coef_, z)}
    return {"method": "Hệ số Ridge × giá trị chuẩn hóa (đóng góp vào mức thay đổi AQI)",
            "contributions": contributions, "sentences": generate_explanations(contributions, latest)}


# ------------------------------- 5. Ghép lại cho giao diện

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
    for horizon in HORIZONS:
        data = supervised_table(weather_hourly, air_hourly, horizon, peak=True)
        for threshold in thresholds:
            suite["classification"][threshold][horizon] = _fit_classifier(data, horizon, threshold)
    tables = {h: supervised_table(weather_hourly, air_hourly, h, peak=False) for h in REGRESSION_HORIZONS}
    suite["regression"] = {h: _fit_regressor(t, h) for h, t in tables.items()}
    suite["ablation"] = _fit_regressor(tables[6], 6, AQI_ONLY)
    main = suite["regression"][6]
    if latest is not None and main["status"] == "ready" and main["selected"] == "ridge":
        suite["explanation"] = _explain_regressor(main["model"], latest, main["features"])
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
            frame = build_feature_frame(weather, air)
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
