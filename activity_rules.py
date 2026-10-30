"""Transparent scoring rules for time-window suggestions.

Health bands follow the official US EPA/AirNow AQI scale, WHO UV Index
guidance, and NOAA/NWS heat-index categories. The 0–100 planner score and
activity weights only rank this user's available forecast hours; they are not
medical thresholds. The selected target group changes the displayed advice,
not the official thresholds or the underlying hourly score.
"""

from __future__ import annotations

import math
from datetime import time
from typing import Any

import numpy as np
import pandas as pd

ACTIVITIES = (
    "Chạy bộ",
    "Đón con",
    "Phơi đồ",
    "Đi làm, di chuyển",
    "Mở cửa thông gió",
)

# Utility weights express how strongly each forecast condition affects the
# practical suitability of an activity. They do not alter health thresholds.
ACTIVITY_WEIGHTS = {
    "Chạy bộ": {"air": 0.45, "heat": 0.25, "uv": 0.20, "rain": 0.10},
    "Đón con": {"air": 0.45, "heat": 0.20, "uv": 0.15, "rain": 0.20},
    "Phơi đồ": {"air": 0.35, "heat": 0.15, "uv": 0.15, "rain": 0.35},
    "Đi làm, di chuyển": {"air": 0.45, "heat": 0.15, "uv": 0.10, "rain": 0.30},
    "Mở cửa thông gió": {"air": 0.50, "heat": 0.15, "uv": 0.05, "rain": 0.30},
}


def _number(row: Any, key: str) -> float | None:
    try:
        value = row.get(key)
        value = float(value)
        return value if math.isfinite(value) else None
    except (AttributeError, TypeError, ValueError):
        return None


def heat_index_fahrenheit(temperature_c: float, humidity: float) -> float:
    """NOAA/NWS heat-index approximation (Rothfusz regression with adjustments)."""
    temp_f = temperature_c * 9 / 5 + 32
    rh = min(100.0, max(0.0, humidity))
    simple = 0.5 * (temp_f + 61 + (temp_f - 68) * 1.2 + rh * 0.094)
    simple = (simple + temp_f) / 2
    if temp_f < 80 or simple < 80:
        return simple
    hi = (
        -42.379 + 2.04901523 * temp_f + 10.14333127 * rh
        - 0.22475541 * temp_f * rh - 0.00683783 * temp_f**2
        - 0.05481717 * rh**2 + 0.00122874 * temp_f**2 * rh
        + 0.00085282 * temp_f * rh**2 - 0.00000199 * temp_f**2 * rh**2
    )
    if rh < 13 and 80 <= temp_f <= 112:
        hi -= ((13 - rh) / 4) * math.sqrt(max(0.0, (17 - abs(temp_f - 95)) / 17))
    elif rh > 85 and 80 <= temp_f <= 87:
        hi += ((rh - 85) / 10) * ((87 - temp_f) / 5)
    return hi


def _aqi_risk(value: float) -> float:
    # AirNow health bands: Good 0–50; Moderate 51–100; USG 101–150;
    # Unhealthy 151–200; Very Unhealthy 201–300; Hazardous 301+.
    if value <= 50:
        return 0.0
    if value <= 100:
        return 20.0 + (value - 50) / 50 * 20
    if value <= 150:
        return 40.0 + (value - 100) / 50 * 20
    if value <= 200:
        return 60.0 + (value - 150) / 50 * 20
    if value <= 300:
        return 80.0 + (value - 200) / 100 * 15
    return min(100.0, 95.0 + (value - 300) / 200 * 5)


def _uv_risk(value: float) -> float:
    # WHO UV Index: 0–2 low, 3–7 protection is recommended, 8+ very high.
    if value < 3:
        return value / 3 * 20
    if value < 8:
        return 20.0 + (value - 3) / 5 * 55
    return min(100.0, 75.0 + (value - 8) * 5)


def _heat_risk(index_f: float) -> float:
    # NOAA/NWS heat-index bands: <80, 80–90, 90–103, 103–125, 125°F+.
    if index_f < 80:
        return 0.0
    if index_f < 90:
        return 20.0 + (index_f - 80) * 2
    if index_f < 103:
        return 40.0 + (index_f - 90) * (25 / 13)
    if index_f < 125:
        return 65.0 + (index_f - 103) * (25 / 22)
    return 90.0 + min(10.0, (index_f - 125) * 0.5)


def score_hour(row: Any, activity: str, group: str | None = None) -> dict[str, Any]:
    """Score a forecast hour from available conditions; no AQI means no ranking."""
    del group  # Groups get advice, not locally invented health cutoffs.
    aqi = _number(row, "us_aqi")
    pm_subindex = _number(row, "us_aqi_pm2_5")
    if aqi is None:
        aqi = pm_subindex
    elif pm_subindex is not None:
        aqi = max(aqi, pm_subindex)
    if aqi is None:
        return {"risk_score": np.nan, "status": "unranked", "components": {}}

    components: dict[str, float] = {"air": _aqi_risk(aqi)}
    temperature = _number(row, "temperature_2m")
    humidity = _number(row, "relative_humidity_2m")
    if temperature is not None and humidity is not None:
        components["heat"] = _heat_risk(heat_index_fahrenheit(temperature, humidity))
    uv = _number(row, "uv_index")
    if uv is not None:
        components["uv"] = _uv_risk(uv)
    rain_probability = _number(row, "precipitation_probability")
    precipitation = _number(row, "precipitation")
    if rain_probability is not None or precipitation is not None:
        # Continuous values avoid inventing a separate official rain threshold.
        rain_scores = []
        if rain_probability is not None:
            rain_scores.append(min(100.0, max(0.0, rain_probability)))
        if precipitation is not None:
            rain_scores.append(100 * max(0.0, precipitation) / (1 + max(0.0, precipitation)))
        components["rain"] = max(rain_scores)

    weights = ACTIVITY_WEIGHTS.get(activity, ACTIVITY_WEIGHTS[ACTIVITIES[0]])
    effective_weight = sum(weights[key] for key in components)
    risk = sum(components[key] * weights[key] for key in components) / effective_weight
    # Planner-only display buckets, not official health categories.
    status = "good" if risk < 33 else "caution" if risk < 67 else "avoid"
    return {"risk_score": float(risk), "status": status, "components": components, "aqi_used": aqi}


def _clock_in_window(value: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= value < end
    return value >= start or value < end


def rank_windows(
    hourly: pd.DataFrame,
    activity: str,
    group: str,
    start_time: time,
    end_time: time,
    duration_minutes: int,
    alternatives: int = 2,
) -> list[dict[str, Any]]:
    """Rank complete, consecutive hourly windows by worst hour, then mean risk."""
    if hourly.empty or duration_minutes < 30 or duration_minutes > 120:
        return []
    work = hourly.sort_values("time").reset_index(drop=True).copy()
    count = int(math.ceil(duration_minutes / 60))
    candidates: list[dict[str, Any]] = []
    for start in range(max(0, len(work) - count + 1)):
        window = work.iloc[start : start + count]
        times = pd.to_datetime(window.time)
        if len(window) != count or not all(_clock_in_window(t.time(), start_time, end_time) for t in times):
            continue
        if len(times) > 1 and not (times.diff().dropna() == pd.Timedelta(1, unit="h")).all():
            continue
        scored = [score_hour(row, activity, group) for _, row in window.iterrows()]
        scores = [item["risk_score"] for item in scored]
        if any(not math.isfinite(float(score)) for score in scores):
            continue
        components = {}
        for name in ("air", "heat", "uv", "rain"):
            available = [item["components"][name] for item in scored if name in item["components"]]
            if available:
                components[name] = float(np.mean(available))
        source = "Dự báo ML của project" if "Dự báo ML của project" in set(window.get("aqi_source", [])) else "Dự báo Open-Meteo"
        candidates.append({
            "start": times.iloc[0],
            "end": pd.Timestamp(times.iloc[0]) + pd.Timedelta(duration_minutes, unit="m"),
            "worst_score": float(max(scores)),
            "mean_score": float(np.mean(scores)),
            "status": "good" if max(scores) < 33 else "caution" if max(scores) < 67 else "avoid",
            "components": components,
            "source": source,
            "rows": window.to_dict("records"),
        })
    candidates.sort(key=lambda item: (item["worst_score"], item["mean_score"], item["start"]))
    chosen: list[dict[str, Any]] = []
    for candidate in candidates:
        if all(candidate["end"] <= item["start"] or candidate["start"] >= item["end"] for item in chosen):
            chosen.append(candidate)
        if len(chosen) >= alternatives + 1:
            break
    return chosen


def window_reason(window: dict[str, Any], hourly: pd.DataFrame) -> list[str]:
    """Summarize the two strongest forecast drivers using actual window values."""
    if not window or not window.get("rows"):
        return []
    data = pd.DataFrame(window["rows"])
    parts: list[tuple[float, str]] = []
    aqi_values = pd.to_numeric(data.get("us_aqi"), errors="coerce")
    if aqi_values.notna().any():
        peak = float(aqi_values.max())
        parts.append((window.get("components", {}).get("air", 0), f"AQI dự báo cao nhất {peak:.0f}"))
    uv_values = pd.to_numeric(data.get("uv_index"), errors="coerce")
    if uv_values.notna().any():
        peak_uv = float(uv_values.max())
        parts.append((window.get("components", {}).get("uv", 0), f"UV cao nhất {peak_uv:.0f}"))
    rain_values = pd.to_numeric(data.get("precipitation_probability"), errors="coerce")
    if rain_values.notna().any():
        peak_rain = float(rain_values.max())
        parts.append((window.get("components", {}).get("rain", 0), f"Khả năng mưa cao nhất {peak_rain:.0f}%"))
    temp = pd.to_numeric(data.get("temperature_2m"), errors="coerce")
    rh = pd.to_numeric(data.get("relative_humidity_2m"), errors="coerce")
    if temp.notna().any() and rh.notna().any():
        feels = [heat_index_fahrenheit(t, h) for t, h in zip(temp, rh) if pd.notna(t) and pd.notna(h)]
        if feels:
            celsius = (max(feels) - 32) * 5 / 9
            parts.append((window.get("components", {}).get("heat", 0), f"Chỉ số nóng nhất khoảng {celsius:.0f}°C"))
    parts.sort(key=lambda pair: pair[0], reverse=True)
    return [text for _, text in parts[:2]]

