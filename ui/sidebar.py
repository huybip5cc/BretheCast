"""Sidebar controls and city summaries."""

from __future__ import annotations

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
    value = None
    if air:
        col = AQI_STANDARDS[standard]["column"]
        value = air["current"].get(col)
    if value is not None and pd.notna(value):
        group = st.session_state.get("target_group", TARGET_GROUPS[0])
        advice = recommendation(float(value), group, standard)
        warning_icon = aqi_icon_data("crisis.png")
        st.markdown(f'<div class="side-line side-advice"><img class="side-advice-icon" src="{warning_icon}" alt=""><strong>{advice}</strong></div>', unsafe_allow_html=True)
    city_tile(city)


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
        if st.session_state.get("mode") == "Gợi ý hôm nay":
            st.session_state["mode"] = "Dự báo & gợi ý hoạt động"
        mode = st.segmented_control("Chế độ", options=("Dự báo thời tiết", "AQI", "Dự báo & gợi ý hoạt động"), default="Dự báo thời tiết", label_visibility="collapsed", key="mode") or "Dự báo thời tiết"
    return mode
