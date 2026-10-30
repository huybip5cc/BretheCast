"""Sidebar controls and city summaries."""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from analysis import AQI_STANDARDS, category
from cities import CITIES
from data import current_weather_age_label
from health import TARGET_GROUPS, recommendation
from ui.assets import aqi_icon_data, city_svg, fmt, weather_icon, weather_text
from ui.widgets import air_info_button


def sidebar_city_selector() -> str:
    st.markdown('<div class="location-label">CHỌN THÀNH PHỐ</div>', unsafe_allow_html=True)
    return st.segmented_control("Thành phố", options=tuple(CITIES), default="Hà Nội", label_visibility="collapsed", key="city") or "Hà Nội"


def city_tile(city: str) -> None:
    st.markdown(f'<div class="city-tile">{city_svg(city)}<div class="caption">{city} <span style="font-weight:400;opacity:.85">· {CITIES[city]["landmark"]}</span></div></div>', unsafe_allow_html=True)


def weather_sidebar(city: str, weather: dict, air: dict | None, standard: str):
    current = weather["current"]
    code = current.get("weather_code")
    label, _ = weather_text(code)
    temp = current.get("temperature_2m")
    shown_temp = "—" if temp is None else f"{int(round(float(temp)))}°C"
    hour = current_weather_age_label(weather)
    updated = pd.to_datetime(current.get("time"), errors="coerce")
    day = updated.strftime("%A") if pd.notna(updated) else "Hôm nay"
    day_vi = {"Monday":"Thứ hai", "Tuesday":"Thứ ba", "Wednesday":"Thứ tư", "Thursday":"Thứ năm", "Friday":"Thứ sáu", "Saturday":"Thứ bảy", "Sunday":"Chủ nhật"}.get(day, day)
    st.markdown(f'<div class="weather-hero">{weather_icon(code, 220, label)}<div class="temperature">{shown_temp}</div><div class="date">{day_vi}<span>, {hour}</span></div></div><div class="side-divider"></div><div class="side-line">{weather_icon(code, 24, label)} <strong>{label}</strong></div>', unsafe_allow_html=True)
    hourly_now = current.get("hourly_metrics", {})
    probability = hourly_now.get("precipitation_probability")
    rain = f"{fmt(probability)}%" if probability is not None and pd.notna(probability) else "—"
    st.markdown(f'<div class="side-line">{weather_icon(61, 24, "Mưa")} <strong>Khả năng mưa · {rain}</strong></div>', unsafe_allow_html=True)
    if air:
        col = AQI_STANDARDS[standard]["column"]
        value = air["current"].get(col)
    if value is not None and pd.notna(value):
        group = st.session_state.get("target_group", TARGET_GROUPS[0])
        advice = recommendation(float(value), group, standard)
        warning_icon = aqi_icon_data("crisis.png")
        st.markdown(f'<div class="side-line side-advice"><img class="side-advice-icon" src="{warning_icon}" alt=""><strong>{advice}</strong></div>', unsafe_allow_html=True)
    city_tile(city)


def aqi_gauge_svg(value, standard: str, color: str) -> str:
    """Draw the sidebar AQI gauge with one shared scale for track, progress and needle."""
    maximum = 500 if standard == "US AQI" else 150
    boundaries = (50, 100, 150, 200, 300) if standard == "US AQI" else (20, 40, 60, 80, 100)
    cx, cy, radius = 130.0, 128.0, 75.0
    start_x, end_x = cx - radius, cx + radius
    valid = value is not None and pd.notna(value)
    ratio = min(max(float(value) / maximum, 0.0), 1.0) if valid else 0.0
    angle = math.pi * (1.0 - ratio)
    needle_r = 55.0
    needle_x = cx + needle_r * math.cos(angle)
    needle_y = cy - needle_r * math.sin(angle)
    value_label = fmt(value) if valid else "chưa có"
    parts = [
        '<svg viewBox="0 0 260 166" width="245" height="166" role="img" '
        f'aria-label="Đồng hồ {standard}: {value_label}">',
        f'<path d="M {start_x:.1f} {cy:.1f} A {radius:.1f} {radius:.1f} 0 0 1 {end_x:.1f} {cy:.1f}" '
        'fill="none" stroke="#eceef1" stroke-width="12" stroke-linecap="round"/>',
    ]
    if valid and ratio > 0:
        progress_x = cx + radius * math.cos(angle)
        progress_y = cy - radius * math.sin(angle)
        parts.append(
            f'<path d="M {start_x:.1f} {cy:.1f} A {radius:.1f} {radius:.1f} 0 0 1 '
            f'{progress_x:.1f} {progress_y:.1f}" fill="none" stroke="{color}" '
            'stroke-width="12" stroke-linecap="round"/>'
        )
    for tick in boundaries:
        tick_angle = math.pi * (1.0 - tick / maximum)
        outer_r, inner_r = radius + 10, radius - 5
        x1, y1 = cx + outer_r * math.cos(tick_angle), cy - outer_r * math.sin(tick_angle)
        x2, y2 = cx + inner_r * math.cos(tick_angle), cy - inner_r * math.sin(tick_angle)
        parts.append(f'<path d="M {x1:.1f} {y1:.1f} L {x2:.1f} {y2:.1f}" stroke="#c9cdd3" stroke-width="1.5"/>')
    if valid:
        parts.extend([
            f'<path d="M {cx:.1f} {cy:.1f} L {needle_x:.1f} {needle_y:.1f}" '
            f'stroke="{color}" stroke-width="3.5" stroke-linecap="round"/>',
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5.5" fill="white" stroke="{color}" stroke-width="3"/>',
        ])
    parts.append('</svg>')
    return ''.join(parts)


def aqi_sidebar(city: str, air: dict, standard: str):
    col = AQI_STANDARDS[standard]["column"]
    current = air["current"]
    value = current.get(col)
    cat, color = category(value, standard)
    pm = current.get("pm2_5")
    pm_index = current.get("us_aqi_pm2_5" if standard == "US AQI" else "european_aqi_pm2_5")
    pm_cat, pm_color = category(pm_index, standard)
    current_time = current.get("time")
    stamp = pd.to_datetime(current_time, errors="coerce")
    time_label = stamp.strftime("%d/%m/%Y · %H:%M") if pd.notna(stamp) else "Không rõ"
    retrieval = air["updated_at"].strftime("%H:%M · %d/%m/%Y") if air.get("updated_at") is not None else "API hiện không kết nối"
    stamp_copy = f'Thời điểm mô hình: {time_label}<br>Truy xuất dữ liệu: {retrieval}'
    if air.get("archive_only"):
        stamp_copy = "API hiện không kết nối · chỉ xem lịch sử mô hình đã lưu"
    st.markdown(f'<div class="aqi-number-ring" style="--aqi-color:{color}"><div class="aqi-number">{fmt(value)}</div></div><div class="aqi-unit aqi-unit-with-help">{standard}{air_info_button("aqi", standard)}</div><div class="aqi-category" style="color:{color}">{cat}</div><div class="aqi-meta">{stamp_copy}</div><div class="side-divider"></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="side-line"><span class="status-dot" style="background:{color}"></span> Chất lượng không khí · {cat}</div><div class="side-line"><span style="font-size:13px;color:#777">PM₂.₅</span> {fmt(pm,1)} µg/m³<br><span style="font-size:11px;color:{pm_color};margin-left:43px">{pm_cat} · chỉ số PM₂.₅</span></div>', unsafe_allow_html=True)
    city_tile(city)


def mode_picker() -> str:
    with st.container(key="mode-switch"):
        mode = st.segmented_control("Chế độ", options=("Dự báo thời tiết", "AQI", "Gợi ý hôm nay"), default="Dự báo thời tiết", label_visibility="collapsed", key="mode") or "Dự báo thời tiết"
    return mode
