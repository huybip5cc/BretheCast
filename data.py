"""Open-Meteo API clients and response validation."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

import pandas as pd
import requests
import streamlit as st

from cities import CITIES, TIMEZONE
from history_store import load_archive, store_archive

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
TIMEOUT = 15


class DataUnavailable(RuntimeError):
    """Raised when an API is unreachable or returns malformed data."""


def _fetch(url: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise DataUnavailable("Không thể kết nối nguồn dữ liệu lúc này.") from exc
    if not isinstance(payload, dict) or payload.get("error"):
        raise DataUnavailable("Nguồn dữ liệu trả về phản hồi không hợp lệ.")
    return payload


def _hourly_frame(payload: dict[str, Any], required: tuple[str, ...]) -> pd.DataFrame:
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict) or not isinstance(hourly.get("time"), list):
        raise DataUnavailable("Nguồn thời tiết không trả về dự báo theo giờ.")
    length = len(hourly["time"])
    values: dict[str, Any] = {"time": hourly["time"]}
    for name in required:
        series = hourly.get(name)
        if not isinstance(series, list) or len(series) != length:
            values[name] = [None] * length
        else:
            values[name] = series
    frame = pd.DataFrame(values)
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
    frame = frame.dropna(subset=["time"]).copy()
    for name in required:
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
    return frame


@st.cache_data(ttl=1800, show_spinner=False)
def get_weather(city: str) -> dict[str, Any]:
    location = CITIES[city]
    payload = _fetch(
        WEATHER_URL,
        {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "timezone": TIMEZONE,
            "past_days": 30,
            "forecast_days": 7,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,showers,snowfall,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m",
            "hourly": "temperature_2m,relative_humidity_2m,visibility,precipitation,precipitation_probability,surface_pressure,uv_index,wind_speed_10m,wind_direction_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,uv_index_max,precipitation_probability_max,wind_speed_10m_max,wind_direction_10m_dominant",
        },
    )
    current = payload.get("current")
    daily = payload.get("daily")
    if not isinstance(current, dict) or not isinstance(daily, dict) or not daily.get("time"):
        raise DataUnavailable("Nguồn thời tiết không trả về thời tiết hiện tại hoặc dự báo.")
    hourly_fields = ("temperature_2m", "relative_humidity_2m", "visibility", "precipitation", "precipitation_probability", "surface_pressure", "uv_index", "wind_speed_10m", "wind_direction_10m")
    hourly = _hourly_frame(payload, hourly_fields)
    now = pd.Timestamp.now(tz=TIMEZONE).tz_localize(None)
    hourly["is_forecast"] = hourly["time"] > now
    hourly["date"] = hourly["time"].dt.date
    current_hour = pd.to_datetime(current.get("time"), errors="coerce")
    if pd.notna(current_hour) and not hourly.empty:
        nearest_idx = (hourly["time"] - current_hour).abs().idxmin()
        nearest = hourly.loc[nearest_idx]
        current["hourly_metrics"] = nearest.to_dict() if abs(nearest["time"] - current_hour) <= pd.Timedelta(hours=1) else {}
    else:
        current["hourly_metrics"] = {}
    try:
        daily_frame = pd.DataFrame(daily)
    except ValueError as exc:
        raise DataUnavailable("Dữ liệu dự báo theo ngày không đồng nhất.") from exc
    daily_frame["time"] = pd.to_datetime(daily_frame["time"], errors="coerce")
    daily_frame = daily_frame.loc[daily_frame["time"].dt.date >= now.date()].reset_index(drop=True)
    return {"current": current, "daily": daily_frame, "hourly": hourly, "updated_at": now}


@st.cache_data(ttl=1800, show_spinner=False)
def get_air_quality(city: str) -> dict[str, Any]:
    location = CITIES[city]
    fields = ("us_aqi", "european_aqi", "us_aqi_pm2_5", "european_aqi_pm2_5", "pm2_5", "pm10", "nitrogen_dioxide", "ozone", "sulphur_dioxide", "carbon_monoxide")
    payload = _fetch(
        AIR_URL,
        {
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "timezone": TIMEZONE,
            "forecast_days": 7,
            "past_days": 30,
            "current": "us_aqi,european_aqi,us_aqi_pm2_5,european_aqi_pm2_5,pm2_5",
            "hourly": ",".join(fields),
        },
    )
    current = payload.get("current")
    if not isinstance(current, dict):
        raise DataUnavailable("Nguồn không khí không trả về chỉ số hiện tại.")
    hourly = _hourly_frame(payload, fields)
    now = pd.Timestamp.now(tz=TIMEZONE).tz_localize(None)
    hourly["is_forecast"] = hourly["time"] > now
    hourly["date"] = hourly["time"].dt.date
    try:
        store_archive(city, hourly)
    except (OSError, sqlite3.Error) as exc:
        logging.warning("Unable to persist AQI archive for %s: %s", city, exc)
    for field in ("us_aqi", "european_aqi", "us_aqi_pm2_5", "european_aqi_pm2_5", "pm2_5"):
        value = current.get(field)
        current[field] = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    archive = load_archive(city)
    if not archive.empty:
        hourly = pd.concat([archive, hourly], ignore_index=True, sort=False)
        hourly = hourly.drop_duplicates(subset="time", keep="last").sort_values("time").reset_index(drop=True)
    return {
        "current": current,
        "hourly": hourly,
        "updated_at": now,
        "timezone": payload.get("timezone", TIMEZONE),
        "units": payload.get("hourly_units", {}),
        "today": now.date(),
    }


def current_weather_age_label(data: dict[str, Any]) -> str:
    timestamp = pd.to_datetime(data["current"].get("time"), errors="coerce")
    return timestamp.strftime("%H:%M") if pd.notna(timestamp) else "—"
