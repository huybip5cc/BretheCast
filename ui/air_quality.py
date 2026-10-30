"""AQI forecast, insights, and chart views."""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from analysis import (
    AQI_STANDARDS, available_history, category, daily_aqi, daily_aqi_range,
    hourly_aqi_pattern, hottest_pattern_period,
)
from health import TARGET_GROUPS, impact_summary, pm25_recommendation, recommendation
from ui.assets import aqi_forecast_icon_filename, aqi_icon_data, fmt
from ui.widgets import air_info_button, card, daily_aqi_card, pm25_gauge_markup, time_insight_card


def forecast_aqi(air: dict, standard: str):
    st.markdown('<div class="section-title">5 ngày tới</div>', unsafe_allow_html=True)
    future = air["hourly"].loc[air["hourly"].is_forecast].copy()
    daily = daily_aqi(future, standard, forecast=True)
    cards = []
    days_vi = ("Thứ hai", "Thứ ba", "Thứ tư", "Thứ năm", "Thứ sáu", "Thứ bảy", "Chủ nhật")
    for _, row in daily.head(5).iterrows():
        d = row["date"]
        cat, color = category(row["aqi"], standard)
        icon_src = aqi_icon_data(aqi_forecast_icon_filename(cat))
        cards.append(f'<div class="forecast-card"><div class="forecast-day">{days_vi[d.weekday()]}</div><div class="forecast-icon"><img class="aqi-weather-icon" src="{icon_src}" alt=""></div><div class="forecast-value" style="color:{color}">{fmt(row["aqi"])}</div><div class="forecast-sub">{cat}</div></div>')
    if cards:
        st.markdown(f'<div class="forecast-grid aqi-forecast-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="chart-card">Dự báo AQI hiện tạm thời không khả dụng.</div>', unsafe_allow_html=True)


def aqi_insights(air: dict, standard: str):
    st.markdown('<div class="section-title">Thông tin chất lượng không khí</div>', unsafe_allow_html=True)
    frame = air["hourly"]
    history = available_history(frame, standard)
    daily = daily_aqi(history, standard)
    col = AQI_STANDARDS[standard]["column"]
    current = air["current"].get(col)
    group = st.session_state.get("target_group", TARGET_GROUPS[0])
    if len(daily):
        last_day = daily.iloc[-1]
        avg = last_day["aqi"]
        avg_footer = impact_summary(avg, standard)
    else:
        avg, avg_footer = None, "—"
    now = pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").tz_localize(None)
    next_24h = frame.loc[
        frame.is_forecast & (frame.time > now) & (frame.time <= now + timedelta(hours=24))
    ].dropna(subset=[col])
    if not next_24h.empty:
        peak = next_24h.loc[next_24h[col].idxmax()]
        peak_value = peak[col]
        peak_time = peak.time.strftime("%H:%M")
        peak_footer = recommendation(peak_value, group, standard)
        low = next_24h.loc[next_24h[col].idxmin()]
        low_time = low.time.strftime("%H:%M")
        low_footer = recommendation(low[col], group, standard)
    else:
        peak_time, peak_footer = "—", "—"
        low_time, low_footer = "—", "—"
    pm = air["current"].get("pm2_5")
    pm_value = None if pm is None or pd.isna(pm) else float(pm)
    pm_advice = pm25_recommendation(pm_value, group, standard)
    pattern = hottest_pattern_period(history, standard)
    pattern_value, pattern_footer = (pattern[0], impact_summary(pattern[1], standard)) if pattern else ("—", "—")
    advice = recommendation(current, group, standard)
    cat, color = category(current, standard)
    entries = (
        ("AQI trung bình ngày", fmt(avg), avg_footer),
        ("Giờ AQI cao nhất 24 giờ tới", peak_time, peak_footer),
        ("PM₂.₅ hiện tại", "", ""),
        ("Khung 3 giờ AQI thường cao", pattern_value, pattern_footer),
        ("Giờ AQI thấp nhất 24 giờ tới", low_time, low_footer),
        ("Khuyến nghị sức khỏe", f'<span style="font-size:17px;color:{color}">{cat}</span>', f'<div class="advice-copy">{advice}</div>'),
    )
    with st.container(key="aqi-insights-grid"):
        for ridx in range(2):
            row_key = f"aqi-insights-row-{ridx + 1}"
            with st.container(key=row_key):
                row = st.columns(3, gap=None)
                for cidx in range(3):
                    idx = ridx * 3 + cidx
                    with row[cidx]:
                        if idx == 0:
                            daily_aqi_card(avg, avg_footer, standard)
                        elif idx in (1, 3, 4):
                            time_insight_card(*entries[idx])
                        elif idx == 2:
                            gauge = pm25_gauge_markup(pm_value, standard)
                            st.markdown(
                                f'<div class="metric-card compact pm25-card">{air_info_button("pm25", standard)}'
                                '<div class="metric-label">PM₂.₅ hiện tại</div>'
                                f'{gauge}'
                                '<div class="pm25-details">'
                                f'<div class="pm25-advice">{pm_advice}</div>'
                                '</div></div>',
                                unsafe_allow_html=True,
                            )
                        elif idx == 5:
                            with st.container(key="health-advisory"):
                                st.markdown('<div class="metric-label">Khuyến nghị sức khỏe</div>', unsafe_allow_html=True)
                                st.selectbox("Nhóm mục tiêu", TARGET_GROUPS, key="target_group", label_visibility="collapsed")
                                st.markdown(f'<div class="advice-copy">{recommendation(current, st.session_state.get("target_group", TARGET_GROUPS[0]), standard)}</div>', unsafe_allow_html=True)
                        else:
                            card(*entries[idx], compact=True)
    st.markdown('<div class="source-note">AQI/PM₂.₅ và chuỗi quá khứ là ước tính mô hình CAMS qua Open‑Meteo, không phải số đo trạm quan trắc. Trung bình ngày dùng trung bình số học các giờ có dữ liệu.</div>', unsafe_allow_html=True)


def chart_layout():
    layout = go.Layout(
        height=280, margin=dict(l=8, r=12, t=8, b=24), paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Poppins, sans-serif", color="#7e8187", size=11),
        xaxis=dict(showgrid=False, zeroline=False, showline=False, tickformat="%d %b · %H:%M", nticks=7),
        yaxis=dict(showgrid=True, gridcolor="#f0f0f2", zeroline=False, showline=False, rangemode="tozero", title=None),
        hovermode="x unified", showlegend=True, legend=dict(orientation="h", y=1.12, x=0),
    )
    return layout


def add_sky_gradient_bars(
    fig,
    x,
    values,
    *,
    customdata=None,
    hovertemplate=None,
    name="",
    base=None,
    width=None,
    opacity=1.0,
    showlegend=False,
    legendgroup=None,
    segments=12,
    secondary_y=None,
):
    """Render thin bar slices as a soft, top-to-bottom sky-blue gradient."""
    heights = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    if base is None:
        bottoms = np.zeros(len(heights), dtype=float)
    elif np.isscalar(base):
        bottoms = np.full(len(heights), float(base), dtype=float)
    else:
        bottoms = pd.to_numeric(pd.Series(base), errors="coerce").to_numpy(dtype=float)
    low_rgb, high_rgb = (222, 241, 251), (91, 164, 218)
    slice_heights = heights / segments
    for index in range(segments):
        level = index / (segments - 1)
        rgb = tuple(round(low_rgb[i] + (high_rgb[i] - low_rgb[i]) * level) for i in range(3))
        alpha = 0.42 + 0.23 * level
        slice_base = bottoms + slice_heights * index
        trace = go.Bar(
            x=x,
            y=slice_heights,
            base=slice_base,
            width=width,
            name=name,
            legendgroup=legendgroup or name,
            showlegend=showlegend and index == segments - 1,
            marker=dict(color=f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{alpha:.2f})", line=dict(width=0)),
            opacity=opacity,
            customdata=customdata,
            hovertemplate=hovertemplate,
            hoverinfo="skip" if hovertemplate is None else None,
        )
        if secondary_y is None:
            fig.add_trace(trace)
        else:
            fig.add_trace(trace, secondary_y=secondary_y)


def aqi_history(air: dict, standard: str):
    st.markdown('<div class="section-title">Lịch sử AQI</div><div class="section-note">Giá trị quá khứ là ước tính CAMS đã lưu; phần sau “Bây giờ” là dự báo Open-Meteo.</div>', unsafe_allow_html=True)
    period = st.radio("Khoảng thời gian", ("24 giờ", "7 ngày", "30 ngày", "90 ngày"), horizontal=True, label_visibility="collapsed", key="aqi_period")
    compare_pm = st.checkbox("So sánh PM₂.₅", value=False, key="aqi_compare_pm")
    frame = air["hourly"].copy()
    col = AQI_STANDARDS[standard]["column"]
    now = pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").tz_localize(None)
    span_hours = {"24 giờ": 24, "7 ngày": 168, "30 ngày": 720, "90 ngày": 2160}[period]
    lower = now - timedelta(hours=span_hours)
    upper = now + timedelta(hours=24)
    frame = frame.loc[(frame.time >= lower) & (frame.time <= upper)].copy()
    past = frame.loc[(~frame.is_forecast) & frame[col].notna()].copy()
    future = frame.loc[frame.is_forecast & frame[col].notna()].copy()
    if past.empty and future.empty:
        st.markdown('<div class="chart-card">Biểu đồ AQI trong khoảng thời gian này hiện tạm thời không khả dụng.</div>', unsafe_allow_html=True)
        return

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    if period == "24 giờ":
        past_colors = [category(value, standard)[1] for value in past[col]]
        future_colors = [category(value, standard)[1] for value in future[col]]
        if not past.empty:
            past_custom = [[category(value, standard)[0], row.pm2_5] for value, row in zip(past[col], past.itertuples())]
            fig.add_trace(go.Bar(x=past.time, y=past[col], name="Mô hình lưu trữ", marker=dict(color=past_colors), opacity=.9, customdata=past_custom, hovertemplate="%{x|%d/%m %H:%M}<br>AQI %{y:.0f} · %{customdata[0]}<br>PM₂.₅ %{customdata[1]:.1f} µg/m³<extra></extra>"), secondary_y=False)
        if not future.empty:
            future_custom = [[category(value, standard)[0], row.pm2_5] for value, row in zip(future[col], future.itertuples())]
            fig.add_trace(go.Bar(x=future.time, y=future[col], name="Dự báo Open-Meteo", marker=dict(color=future_colors, line=dict(color="#ffffff", width=1)), opacity=.62, customdata=future_custom, hovertemplate="%{x|%d/%m %H:%M}<br>AQI dự báo %{y:.0f} · %{customdata[0]}<br>PM₂.₅ %{customdata[1]:.1f} µg/m³<extra></extra>"), secondary_y=False)
        if compare_pm:
            if not past.empty and past["pm2_5"].notna().any():
                fig.add_trace(go.Scatter(x=past.time, y=past.pm2_5, name="PM₂.₅ · mô hình lưu trữ", mode="lines", line=dict(color="#5362bf", width=1.5), connectgaps=False, hovertemplate="%{x|%d/%m %H:%M}<br>PM₂.₅ %{y:.1f} µg/m³<extra></extra>"), secondary_y=True)
            if not future.empty and future["pm2_5"].notna().any():
                fig.add_trace(go.Scatter(x=future.time, y=future.pm2_5, name="PM₂.₅ · dự báo API", mode="lines", line=dict(color="#bd8b4b", width=1.5, dash="dash"), connectgaps=False, hovertemplate="%{x|%d/%m %H:%M}<br>PM₂.₅ %{y:.1f} µg/m³<extra></extra>"), secondary_y=True)
    else:
        summary = daily_aqi_range(frame, standard)
        past_days = summary.loc[~summary.is_forecast]
        future_days = summary.loc[summary.is_forecast]
        for part, name, opacity, offset in ((past_days, "Mô hình lưu trữ", .88, -0.16), (future_days, "Dự báo Open-Meteo", .58, 0.16)):
            if part.empty:
                continue
            xs = [pd.Timestamp(day) + pd.Timedelta(days=offset) for day in part.date]
            colors = [category(value, standard)[1] for value in part["mean"]]
            custom = [[row.minimum, row.maximum, row.mean, row.hours, category(row.mean, standard)[0]] for row in part.itertuples()]
            fig.add_trace(go.Bar(x=xs, y=part.maximum - part.minimum, base=part.minimum, width=10 * 60 * 60 * 1000, name=f"Dải min–max · {name.lower()}", marker=dict(color=colors, line=dict(color="#ffffff", width=1)), opacity=opacity, customdata=custom, hovertemplate="%{x|%d/%m}<br>Thấp nhất %{customdata[0]:.0f}<br>Cao nhất %{customdata[1]:.0f}<br>Trung bình %{customdata[2]:.0f} · %{customdata[4]}<br>%{customdata[3]} giờ có mẫu<extra></extra>"), secondary_y=False)
            fig.add_trace(go.Scatter(x=xs, y=part["mean"], name=f"AQI trung bình · {name.lower()}", mode="markers", marker=dict(color="#202124" if not part.is_forecast.any() else "#a46d35", size=6, symbol="circle"), customdata=[[category(value, standard)[0]] for value in part["mean"]], hovertemplate="%{x|%d/%m}<br>Trung bình %{y:.0f} · %{customdata[0]}<extra></extra>"), secondary_y=False)
        if compare_pm:
            for source, name, color in ((False, "PM₂.₅ · mô hình lưu trữ", "#5362bf"), (True, "PM₂.₅ · dự báo API", "#bd8b4b")):
                subset = frame.loc[frame.is_forecast.eq(source)].dropna(subset=["pm2_5"])
                if not subset.empty:
                    pm_daily = subset.groupby("date", as_index=False).pm2_5.mean()
                    fig.add_trace(go.Scatter(x=pm_daily.date, y=pm_daily.pm2_5, name=name, mode="lines+markers", line=dict(color=color, width=1.5, dash="dash" if source else "solid"), marker=dict(size=4), connectgaps=False, hovertemplate="%{x|%d/%m}<br>PM₂.₅ trung bình %{y:.1f} µg/m³<extra></extra>"), secondary_y=True)

    for trace in list(fig.data):
        if trace.type == "bar":
            trace.visible = False
            is_forecast_trace = "Open-Meteo" in str(trace.name)
            add_sky_gradient_bars(
                fig, trace.x, trace.y, base=trace.base, width=trace.width,
                customdata=trace.customdata, hovertemplate=trace.hovertemplate,
                name=trace.name, legendgroup=trace.legendgroup or trace.name,
                opacity=trace.opacity if trace.opacity is not None else (0.62 if is_forecast_trace else 0.9),
                showlegend=trace.showlegend is not False,
            )
        elif trace.type == "scatter" and "PM₂.₅" in str(trace.name or ""):
            is_forecast_trace = "dự báo" in str(trace.name).lower() or "api" in str(trace.name).lower()
            trace.line.color = "#7fb9dc" if is_forecast_trace else "#4c97c4"
            trace.line.width = 1.2
            trace.marker.size = 3

    max_value = max([float(value) for value in pd.concat([past[col], future[col]]) if pd.notna(value)] + [100.0])
    chart_top = max(max_value * 1.12, 150 if standard == "EU AQI" else 500)
    fig.add_vrect(x0=now, x1=upper, fillcolor="rgba(116,184,224,0.045)", line_width=0, layer="below")
    fig.add_vline(x=now, line=dict(color="#89aec4", width=0.8, dash="dot"), annotation_text="Bây giờ", annotation_position="top")
    fig.update_layout(
        height=315, barmode="overlay", bargap=0.28, margin=dict(l=8, r=12, t=24, b=24),
        paper_bgcolor="white", plot_bgcolor="white", font=dict(family="Poppins, sans-serif", color="#7f8d97", size=11),
        hovermode="x unified", showlegend=True, legend=dict(orientation="h", y=1.12, x=0),
        xaxis=dict(showgrid=False, zeroline=False, showline=False, tickfont=dict(color="#82919a"), tickformat="%d %b · %H:%M" if period == "24 giờ" else "%d %b", nticks=9),
        yaxis=dict(showgrid=True, gridcolor="rgba(108,166,201,.14)", gridwidth=0.7, zeroline=False, showline=False, range=[0, chart_top], title="AQI"),
        yaxis2=dict(showgrid=False, zeroline=False, showline=False, title="PM₂.₅ (µg/m³)", rangemode="tozero", overlaying="y", side="right", visible=compare_pm),
    )
    with st.container():
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.markdown('<div class="source-note">Các giờ không có mẫu được để trống; không nối hoặc nội suy. CAMS là mô hình, không phải số đo tại trạm.</div>', unsafe_allow_html=True)


def pollution_hourly_chart(air: dict, standard: str):
    st.markdown('<div class="section-title">Mô hình ô nhiễm theo giờ</div><div class="section-note">AQI trung bình từng giờ trong các ngày đã lưu, tách ngày thường và cuối tuần.</div>', unsafe_allow_html=True)
    day_type = st.radio("Nhóm ngày", ("Ngày thường", "Cuối tuần"), horizontal=True, label_visibility="collapsed", key="aqi_day_type")
    result = hourly_aqi_pattern(air["hourly"], standard, day_type, minimum_days=3)
    if result is None:
        st.markdown(f'<div class="chart-card">Cần ít nhất 3 ngày {day_type.lower()} có mẫu AQI để so sánh các giờ.</div>', unsafe_allow_html=True)
        return
    hourly, day_count = result
    available = hourly.dropna(subset=["aqi_mean"])
    highest = available.loc[available.aqi_mean.idxmax()]
    lowest = available.loc[available.aqi_mean.idxmin()]
    st.markdown(f'<div class="section-note" style="margin:0 0 10px">{day_type}: AQI trung bình cao nhất lúc {int(highest.hour):02d}:00; thấp nhất lúc {int(lowest.hour):02d}:00.</div>', unsafe_allow_html=True)
    colors = [category(value, standard)[1] if pd.notna(value) else "#e7e8eb" for value in hourly.aqi_mean]
    borders = ["#202124" if hour in (int(highest.hour), int(lowest.hour)) else "#ffffff" for hour in hourly.hour]
    fig = go.Figure(go.Bar(
        x=hourly.hour, y=hourly.aqi_mean, name="AQI trung bình", marker=dict(color=colors, line=dict(color=borders, width=2)),
        customdata=hourly.sample_days, hovertemplate="%{x:02d}:00<br>AQI trung bình %{y:.0f}<br>Có mẫu trong %{customdata} ngày<extra></extra>",
    ))
    source_bars = fig.data[0]
    source_bars.visible = False
    add_sky_gradient_bars(
        fig, source_bars.x, source_bars.y, customdata=source_bars.customdata,
        hovertemplate=source_bars.hovertemplate, name=source_bars.name,
        showlegend=False,
    )
    top = max(float(available.aqi_mean.max()) * 1.2, 100)
    fig.add_annotation(x=int(highest.hour), y=float(highest.aqi_mean), text="Cao nhất", showarrow=True, arrowhead=0, arrowwidth=0.8, arrowcolor="#8ba8bb", ax=0, ay=-26, font=dict(size=10, color="#617b8b"))
    fig.add_annotation(x=int(lowest.hour), y=float(lowest.aqi_mean), text="Thấp nhất", showarrow=True, arrowhead=0, arrowwidth=0.8, arrowcolor="#8ba8bb", ax=0, ay=24, font=dict(size=10, color="#617b8b"))
    fig.update_layout(
        height=280, barmode="overlay", bargap=0.28, margin=dict(l=8, r=12, t=22, b=22), paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Poppins, sans-serif", color="#7e8187", size=11), showlegend=False,
        xaxis=dict(title=None, tickmode="array", tickvals=[0, 3, 6, 9, 12, 15, 18, 21, 23], ticktext=["00", "03", "06", "09", "12", "15", "18", "21", "23"], showgrid=False, range=[-0.6, 23.6]),
        yaxis=dict(title="AQI", showgrid=True, gridcolor="rgba(108,166,201,.14)", gridwidth=0.7, zeroline=False, showline=False, range=[0, top]),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.markdown(f'<div class="source-note">Cơ sở: {day_count} ngày {day_type.lower()}. Mỗi cột hiển thị trung bình các mốc giờ có mẫu; không nội suy giờ trống.</div>', unsafe_allow_html=True)
