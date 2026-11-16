"""Weather forecast and highlight views."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from analysis import AQI_STANDARDS, category
from ui.assets import daypart_illustration, direction, fmt, weather_icon, weather_text
from ui.widgets import card_markup

DAYPARTS = (
    ("morning", "Sáng", 6, 10, 8),
    ("noon", "Trưa", 10, 14, 12),
    ("afternoon", "Chiều", 14, 18, 16),
    ("evening", "Tối", 18, 21, 19),
    ("night", "Đêm", 21, 6, 23),
)


def weather_dayparts(weather: dict):
    """Show an illustrated timeline with representative hourly weather values."""
    hourly = weather.get("hourly")
    if not isinstance(hourly, pd.DataFrame):
        hourly = pd.DataFrame()
    updated_at = pd.to_datetime(weather.get("updated_at"), errors="coerce")
    if pd.isna(updated_at):
        updated_at = pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").tz_localize(None)
    today = updated_at.date()
    tomorrow = (pd.Timestamp(today) + pd.Timedelta(days=1)).date()

    st.markdown(
        '<div class="section-title">Nhịp thời tiết hôm nay</div>'
        '<div class="section-note">Năm khung giờ tiêu biểu, kèm nhiệt độ và khả năng mưa tại mốc giờ trên ảnh.</div>',
        unsafe_allow_html=True,
    )

    cards = []
    has_hourly_times = "time" in hourly and pd.api.types.is_datetime64_any_dtype(hourly["time"])
    for key, label, start_hour, end_hour, target_hour in DAYPARTS:
        sample = pd.DataFrame()
        if has_hourly_times:
            hours = hourly["time"].dt.hour
            dates = hourly["time"].dt.date
            if key == "night":
                mask = ((dates == today) & (hours >= start_hour)) | ((dates == tomorrow) & (hours < end_hour))
            else:
                mask = (dates == today) & (hours >= start_hour) & (hours < end_hour)
            sample = hourly.loc[mask]

        sample_time = "—"
        temperature = "—"
        rain = "—"
        if not sample.empty:
            target = pd.Timestamp(today) + pd.Timedelta(hours=target_hour)
            index = (sample["time"] - target).abs().idxmin()
            row = sample.loc[index]
            sample_time = row["time"].strftime("%H:%M")
            temperature = fmt(row.get("temperature_2m"))
            rain = fmt(row.get("precipitation_probability"))

        end_label = f"{end_hour:02d}:00" if key != "night" else "06:00"
        temperature_markup = (
            f'<span class="daypart-temperature">{temperature}<small>°C</small></span>'
            if temperature != "—" else '<span class="daypart-temperature daypart-missing">—</span>'
        )
        rain_markup = (
            f'<span class="daypart-rain"><span aria-hidden="true">💧</span> {rain}% mưa</span>'
            if rain != "—" else '<span class="daypart-rain daypart-missing">Chưa có xác suất mưa</span>'
        )
        cards.append(
            f'<article class="daypart-card"><div class="daypart-art">{daypart_illustration(key)}'
            f'<span class="daypart-clock">{sample_time}</span></div>'
            f'<div class="daypart-copy"><div class="daypart-heading"><strong>{label}</strong>'
            f'<span>{start_hour:02d}:00–{end_label}</span></div>'
            f'{temperature_markup}<div class="daypart-meta">{rain_markup}</div></div></article>'
        )

    st.markdown(f'<div class="weather-dayparts-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="source-note">Số liệu lấy từ mốc giờ đại diện của Open‑Meteo; khung đêm tính từ 21:00 đến 06:00 hôm sau.</div>',
        unsafe_allow_html=True,
    )


def forecast_weather(weather: dict):
    daily = weather["daily"].head(7)
    cards = []
    day_names = ("Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy", "Chủ nhật")
    for _, row in daily.iterrows():
        code = row.get("weather_code")
        label, _ = weather_text(code)
        dt = row["time"]
        cards.append(f'<div class="forecast-card"><div class="forecast-day">{day_names[dt.weekday()]}</div><div class="forecast-icon" title="{label}">{weather_icon(code, 46, label)}</div><div class="weather-temps">{fmt(row.get("temperature_2m_max"))}° <span>{fmt(row.get("temperature_2m_min"))}°</span></div><div class="forecast-sub">Mưa {fmt(row.get("precipitation_probability_max"))}%</div></div>')
    st.markdown('<div class="section-title">7 ngày tới</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="forecast-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def weather_highlights(weather: dict, air: dict | None, standard: str):
    st.markdown('<div class="section-title">Điểm nhấn hôm nay</div>', unsafe_allow_html=True)
    daily = weather["daily"].iloc[0] if not weather["daily"].empty else {}
    hourly = weather["current"].get("hourly_metrics", {})
    uv = daily.get("uv_index_max") if hasattr(daily, "get") else None
    wind = weather["current"].get("wind_speed_10m")
    sunrise = pd.to_datetime(daily.get("sunrise"), errors="coerce") if hasattr(daily, "get") else pd.NaT
    sunset = pd.to_datetime(daily.get("sunset"), errors="coerce") if hasattr(daily, "get") else pd.NaT
    humidity = hourly.get("relative_humidity_2m")
    visibility = hourly.get("visibility")
    humidity_status = (
        "—" if humidity is None or pd.isna(humidity)
        else "Khô" if float(humidity) < 30
        else "Dễ chịu" if float(humidity) <= 60
        else "Ẩm cao"
    )
    visibility_km = float(visibility) / 1000 if visibility is not None and pd.notna(visibility) else None
    visibility_status = (
        "—" if visibility_km is None
        else "Kém" if visibility_km < 2
        else "Trung bình" if visibility_km < 8
        else "Tốt"
    )
    air_value = air["current"].get(AQI_STANDARDS[standard]["column"]) if air else None
    air_status = category(air_value, standard)[0] if air else "—"
    vals = (
        ("Chỉ số UV", fmt(uv), "Cực đại trong ngày"),
        ("Tốc độ gió", f'{fmt(wind,1)} <small>km/h</small>', f'Hướng {direction(weather["current"].get("wind_direction_10m"))}'),
        ("Sun", f'{sunrise.strftime("%H:%M") if pd.notna(sunrise) else "—"} <small>/</small> {sunset.strftime("%H:%M") if pd.notna(sunset) else "—"}', "Giờ địa phương"),
        ("Độ ẩm", fmt(humidity), humidity_status),
        ("Tầm nhìn", f'{fmt(visibility_km,1) if visibility_km is not None else "—"} <small>km</small>', visibility_status),
        ("Chất lượng không khí", fmt(air_value) if air else "—", air_status),
    )
    cards = "".join(card_markup(*item, standard=standard) for item in vals)
    st.markdown(f'<div class="metric-grid">{cards}</div>', unsafe_allow_html=True)
