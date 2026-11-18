"""Huấn luyện Logistic Regression để ước tính khả năng AQI vượt ngưỡng."""

from __future__ import annotations

import unicodedata
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st
from sklearn.calibration import calibration_curve
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HORIZONS = (6, 12, 24)                # dự báo xác suất sau 6/12/24 giờ
ALERT = 0.25                          # báo động khi xác suất >= 25% (bỏ sót tốn gấp 3 lần báo nhầm: 1/(1+3))

# Ngưỡng US AQI theo thành phố. 
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
WEATHER_COLS = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m", "precipitation", "surface_pressure"]
AIR_COLS = ["us_aqi", "pm2_5"]


def thresholds_for_city(city: str) -> tuple[int, int]:
    key = lambda name: unicodedata.normalize("NFC", str(name)).strip().casefold()
    return tuple({key(k): v for k, v in CITY_THRESHOLDS.items()}.get(key(city), DEFAULT_THRESHOLDS))


# ------------------- 1. Dữ liệu -> bảng (mỗi dòng = một giờ)

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
    }, index=g.index)
    return f.reset_index()


def supervised_table(weather: pd.DataFrame, air: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Build a training table whose target is the highest AQI in the next horizon."""
    return _supervised_feature_table(build_feature_frame(weather, air), horizon)


def _supervised_feature_table(features: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Attach the future AQI peak used to create a threshold-exceedance label."""
    if features.empty:
        return features.assign(target=np.nan)
    f = features.copy()
    seen = f["us_aqi_now"].where(~f["is_forecast"])
    f["target"] = seen.rolling(horizon).max().shift(-horizon)
    return f.loc[~f["is_forecast"]].dropna(subset=[*FEATURES, "target"]).reset_index(drop=True)


def _split(data: pd.DataFrame, horizon: int, test_fraction: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chia theo thời gian: phần cũ để học, 20% mới nhất để thi, chừa H giờ ở giữa để đáp án không bị lộ."""
    times = data["time"].drop_duplicates().sort_values().reset_index(drop=True)
    start = times.iloc[min(int(len(times) * (1 - test_fraction)), len(times) - 1)] if len(times) else pd.NaT
    return data[data.time <= start - pd.Timedelta(hours=horizon)], data[data.time >= start]


# -------------------------- 2. Phân loại: Logistic Regression

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
        # baseline 1: luôn đoán tần suất chung
        climatology=_scores(y, np.full(len(y), base)),          
        # baseline 2: "đang vượt thì sẽ vượt"
        current_over_threshold=_scores(y, (test.us_aqi_now > threshold).astype(float).to_numpy()),  
        
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


# ------------------------------ 3. Ghép lại cho giao diện

@st.cache_resource(show_spinner=False)
def train_city_suite(city: str, weather_hourly: pd.DataFrame, air_hourly: pd.DataFrame) -> dict[str, Any]:
    thresholds = thresholds_for_city(city)
    features = build_feature_frame(weather_hourly, air_hourly)
    history = features.loc[~features.is_forecast.astype(bool)] if not features.empty else features
    complete = history.dropna(subset=list(FEATURES)) if not history.empty else history
    latest = complete.iloc[-1] if not complete.empty else None
    suite: dict[str, Any] = {"city": city, "historical_hours": int(len(history)), "latest": latest, "thresholds": thresholds,
                             "classification": {t: {} for t in thresholds},
                             "status": "ready" if latest is not None else "unavailable"}
    classification_tables = {
        horizon: _supervised_feature_table(features, horizon)
        for horizon in HORIZONS
    }
    for horizon, data in classification_tables.items():
        for threshold in thresholds:
            suite["classification"][threshold][horizon] = _fit_classifier(data, horizon, threshold)
    return suite


def planner_forecast(weather_hourly: pd.DataFrame, air_hourly: pd.DataFrame, hours: int = 48) -> pd.DataFrame:
    """Combine hourly weather with available Open-Meteo AQI forecasts; leave missing AQI blank."""
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
    columns = [c for c in ("time", "us_aqi", "us_aqi_pm2_5", "pm2_5") if c in air]
    result = future.merge(air[columns], on="time", how="left") if columns else future.copy()
    for name in ("us_aqi", "us_aqi_pm2_5"):
        if name not in result:
            result[name] = np.nan
    result["aqi_source"] = np.where(result["us_aqi"].notna(), "Dự báo Open-Meteo", "")
    return result.sort_values("time").reset_index(drop=True)
