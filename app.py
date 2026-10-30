from __future__ import annotations

import pandas as pd
import streamlit as st

from activity_rules import rank_windows
from analysis import AQI_STANDARDS
from data import DataUnavailable, get_air_quality, get_weather
from decision_engine import planner_forecast, train_city_suite
from history_store import load_archive
from ui.air_quality import aqi_history, aqi_insights, forecast_aqi, pollution_hourly_chart
from ui.sidebar import aqi_sidebar, city_tile, mode_picker, sidebar_city_selector, weather_sidebar
from ui.styles import apply_styles
from ui.today import current_preferences, render_today_dashboard, scored_forecast, sidebar_conclusion
from ui.weather import forecast_weather, weather_highlights


st.set_page_config(page_title="Không khí & thời tiết", page_icon="◌", layout="wide", initial_sidebar_state="collapsed")


apply_styles()


with st.container(key="dashboard-layout"):
    left, main = st.columns([.24,.76], gap=None)
    with left:
        with st.container(key="dashboard-sidebar"):
            city = sidebar_city_selector()
            if st.session_state.get("mode", "Dự báo thời tiết") == "AQI":
                st.selectbox("Chỉ số chất lượng không khí", tuple(AQI_STANDARDS), key="aqi_standard")
            sidebar_slot = st.empty()
    with main:
        with st.container(key="dashboard-main"):
            mode = mode_picker()
            main_slot = st.empty()


weather = None


air = None


weather_error = air_error = None


with st.spinner("Đang tải dữ liệu…"):
    try:
        weather = get_weather(city)
    except DataUnavailable as exc:
        weather_error = str(exc)
    try:
        air = get_air_quality(city)
    except DataUnavailable as exc:
        air_error = str(exc)
        archived = load_archive(city)
        if not archived.empty:
            air = {"current": {"us_aqi": None, "european_aqi": None, "us_aqi_pm2_5": None, "european_aqi_pm2_5": None, "pm2_5": None, "time": None}, "hourly": archived, "updated_at": None, "archive_only": True, "timezone": "Asia/Ho_Chi_Minh", "units": {}, "today": pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").date()}


standard = st.session_state.get("aqi_standard", "US AQI")


if mode == "Gợi ý hôm nay":
    preferences = current_preferences()
    suite = None
    forecast = pd.DataFrame()
    if weather and air:
        with st.spinner("Đang kiểm định chuỗi thời tiết và AQI theo thời gian…"):
            suite = train_city_suite(city, weather["hourly"], air["hourly"])
        forecast = planner_forecast(weather["hourly"], air["hourly"], suite.get("regression", {}).get(1))
    elif weather:
        forecast = planner_forecast(weather["hourly"], pd.DataFrame(), None)
    sidebar_forecast = scored_forecast(forecast, preferences["activity"], preferences["group"])
    sidebar_plan = rank_windows(
        sidebar_forecast, preferences["activity"], preferences["group"],
        preferences["start"], preferences["end"], int(preferences["duration"]), alternatives=2,
    )
    with main_slot.container():
        if weather_error:
            st.info(weather_error)
        if air_error:
            st.info(air_error)
        render_today_dashboard(suite, forecast, "US AQI")
        st.markdown('<div class="source-note" style="margin-top:28px">Nguồn dữ liệu: <a href="https://open-meteo.com/" target="_blank">Open‑Meteo</a> · <a href="https://atmosphere.copernicus.eu/" target="_blank">CAMS</a> · Giờ Việt Nam (UTC+7)</div>', unsafe_allow_html=True)
    with sidebar_slot.container():
        sidebar_conclusion(city, sidebar_forecast, sidebar_plan, preferences["activity"], preferences["group"])
        city_tile(city)
else:
    with sidebar_slot.container():
        if mode == "AQI":
            if air:
                aqi_sidebar(city, air, standard)
            else:
                st.markdown('<div class="air-illustration"><span style="font-size:70px;color:#adb0b7">◉</span></div>', unsafe_allow_html=True)
                st.markdown(f'<div class="aqi-number">—</div><div class="aqi-unit">AQI</div><div class="aqi-category">—</div><div class="aqi-meta">{air_error}</div>', unsafe_allow_html=True)
                city_tile(city)
        else:
            if weather:
                weather_sidebar(city, weather, air, standard)
            else:
                st.markdown(f'<div class="weather-hero"><div class="temperature">—</div><div class="aqi-meta">{weather_error}</div></div>', unsafe_allow_html=True)
                city_tile(city)

    with main_slot.container():
        if mode == "AQI" and air and air.get("archive_only"):
            st.markdown('<div class="chart-card" style="margin:4px 0 14px;font-size:12px;color:#777">Nguồn API tạm thời không sẵn sàng. Đang hiển thị chuỗi mô hình đã lưu; AQI và PM₂.₅ hiện tại cùng dự báo được để trống.</div>', unsafe_allow_html=True)
        if mode == "Dự báo thời tiết":
            if weather:
                forecast_weather(weather)
                weather_highlights(weather, air, st.session_state.get("aqi_standard", "US AQI"))
            else:
                st.markdown(f'<div class="chart-card">{weather_error or "Dữ liệu thời tiết hiện không sẵn sàng."}</div>', unsafe_allow_html=True)
        elif air:
            forecast_aqi(air, standard)
            aqi_insights(air, standard)
            aqi_history(air, standard)
            pollution_hourly_chart(air, standard)
        else:
            st.markdown(f'<div class="chart-card">{air_error or "Dữ liệu AQI hiện không sẵn sàng."}</div>', unsafe_allow_html=True)
        st.markdown('<div class="source-note" style="margin-top:28px">Nguồn dữ liệu: <a href="https://open-meteo.com/" target="_blank">Open‑Meteo</a> · <a href="https://atmosphere.copernicus.eu/" target="_blank">CAMS</a> · Giờ Việt Nam (UTC+7)</div>', unsafe_allow_html=True)
