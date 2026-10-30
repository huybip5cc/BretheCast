"""Reusable metric cards, gauges, and AQI guidance."""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from analysis import AQI_STANDARDS, PM25_CONCENTRATION_BANDS, category, pm25_category
from ui.assets import aqi_icon_data, fmt, weather_icon_data


def card(label: str, value: str, footer: str = "", compact: bool = False):
    klass = "metric-card compact" if compact else "metric-card"
    st.markdown(f'<div class="{klass}"><div class="metric-label">{label}</div><div class="metric-value">{value}</div><div class="metric-foot">{footer}</div></div>', unsafe_allow_html=True)


def daily_aqi_card(value, footer: str, standard: str):
    _label, color = category(value, standard)
    help_button = ""
    st.markdown(
        '<div class="metric-card compact daily-average-card">'
        f'<div class="metric-label">AQI trung bình ngày{help_button}</div>'
        f'<div class="daily-aqi-content"><div class="daily-aqi-ring" style="--aqi-color:{color}">'
        f'<strong>{fmt(value)}</strong><span>{standard}</span></div></div>'
        f'<div class="metric-foot">{footer}</div></div>',
        unsafe_allow_html=True,
    )


def time_insight_card(label: str, value: str, footer: str):
    icon_src = aqi_icon_data("clock.png")
    help_button = ""
    st.markdown(
        '<div class="metric-card compact time-insight-card">'
        f'<div class="metric-label">{label}{help_button}</div>'
        f'<div class="time-insight-main"><img class="time-insight-icon" src="{icon_src}" alt="Biểu tượng thời gian">'
        f'<div class="metric-value">{value}</div></div>'
        f'<div class="metric-foot">{footer}</div></div>',
        unsafe_allow_html=True,
    )


def air_info_button(kind: str, standard: str = "US AQI") -> str:
    if kind == "pm25":
        title = "PM₂.₅ là gì?"
        definition = (
            "PM₂.₅ là bụi mịn có đường kính không quá 2,5 µm. Hạt nhỏ có thể đi sâu vào phổi; "
            "phơi nhiễm có liên quan đến bệnh hô hấp và tim mạch."
        )
        bands = PM25_CONCENTRATION_BANDS[standard]
        effects = (
            "Không khí tương đối sạch; nguy cơ thấp.",
            "Đa số ít bị ảnh hưởng; người nhạy cảm nên chú ý triệu chứng.",
            "Người nhạy cảm cân nhắc giảm vận động gắng sức ngoài trời.",
            "Nên hạn chế vận động kéo dài hoặc gắng sức ngoài trời.",
            "Nguy cơ tăng; giảm hoạt động ngoài trời, nhất là với nhóm nhạy cảm.",
            "Mức rất cao; tránh hoạt động gắng sức ngoài trời.",
        )
        source = '<a href="https://www.who.int/news/item/25-06-2024-what-are-health-consequences-of-air-pollution-on-populations" target="_blank" rel="noopener">WHO · tác động của bụi mịn</a>'
        note = "Các mốc nồng độ trong ứng dụng là mức tham khảo theo chuẩn đã chọn; ảnh hưởng còn tùy thời gian tiếp xúc và tình trạng sức khỏe."
    else:
        title = f"{standard} là gì?"
        definition = "AQI biến mức ô nhiễm không khí thành một con số dễ hiểu. Chỉ số càng cao, nguy cơ ảnh hưởng sức khỏe càng lớn."
        bands = AQI_STANDARDS[standard]["bands"]
        if standard == "US AQI":
            effects = (
                "Không khí tốt; nguy cơ thấp.",
                "Đa số ổn; người rất nhạy cảm có thể bị ảnh hưởng.",
                "Người nhạy cảm có thể gặp triệu chứng; nên giảm gắng sức ngoài trời.",
                "Một số người có thể bị ảnh hưởng; nhóm nhạy cảm có thể nặng hơn.",
                "Nguy cơ sức khỏe tăng đối với mọi người.",
                "Cảnh báo sức khỏe; mọi người dễ bị ảnh hưởng.",
            )
            source = '<a href="https://www.airnow.gov/aqi/aqi-basics/" target="_blank" rel="noopener">AirNow / US EPA · các mức AQI</a>'
        else:
            effects = (
                "Có thể sinh hoạt ngoài trời như thường lệ.",
                "Có thể sinh hoạt ngoài trời như thường lệ.",
                "Người nhạy cảm cân nhắc giảm hoạt động mạnh ngoài trời nếu có triệu chứng.",
                "Giảm vận động gắng sức nếu có triệu chứng; nhóm nhạy cảm nên thận trọng hơn.",
                "Nhóm nhạy cảm nên giảm hoạt động thể chất ngoài trời.",
                "Nên tránh hoạt động thể chất ngoài trời.",
            )
            source = '<a href="https://airindex.eea.europa.eu/AQI/" target="_blank" rel="noopener">EEA · European Air Quality Index</a>'
        note = "Mức tác động là hướng dẫn chung; trẻ nhỏ, người cao tuổi và người có bệnh tim phổi thường nhạy cảm hơn."

    rows = []
    previous = None
    for index, (ceiling, label, _color) in enumerate(bands):
        if index == 0:
            range_label = f"0–{ceiling:g}" if math.isfinite(ceiling) else "0 trở lên"
        elif math.isfinite(ceiling):
            range_label = f">{previous:g}–{ceiling:g}"
        else:
            range_label = f">{previous:g}"
        rows.append(f"<li><b>{range_label} · {label}:</b> {effects[min(index, len(effects)-1)]}</li>")
        previous = ceiling
    body = (
        f'<details class="air-info"><summary aria-label="Giải thích {title}" title="Giải thích">?</summary>'
        f'<div class="air-info-note"><strong>{title}</strong><p>{definition}</p>'
        f'<p><b>Các mức và ảnh hưởng:</b></p><ul>{"".join(rows)}</ul>'
        f'<p>{note}</p><div class="air-info-sources">Nguồn: {source}</div></div></details>'
    )
    return body


def uv_color(value) -> str:
    if value is None or pd.isna(value):
        return "#b9bdc4"
    value = float(value)
    if value <= 2:
        return "#66a874"
    if value <= 5:
        return "#d4ad37"
    if value <= 7:
        return "#e88c3d"
    if value <= 10:
        return "#d85e58"
    return "#8c63a9"


def uv_gauge(value, displayed_value: str = "—") -> str:
    is_missing = value is None or pd.isna(value)
    number = 0.0 if is_missing else min(12.0, max(0.0, float(value)))
    color = uv_color(None if is_missing else number)
    radius = 95
    arc_length = math.pi * radius
    dash_offset = arc_length * (1 - number / 12.0)
    rotation = number / 12.0 * 180
    ticks = []
    tick_marks = []
    for tick in (0, 3, 6, 9, 12):
        angle = math.pi - tick / 12.0 * math.pi
        x = 120 + 113 * math.cos(angle)
        y = 120 - 113 * math.sin(angle) + 4
        ticks.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" class="uv-tick">{tick}</text>')
        inner_x = 120 + 86 * math.cos(angle)
        inner_y = 120 - 86 * math.sin(angle)
        outer_x = 120 + 103 * math.cos(angle)
        outer_y = 120 - 103 * math.sin(angle)
        tick_marks.append(f'<line x1="{inner_x:.1f}" y1="{inner_y:.1f}" x2="{outer_x:.1f}" y2="{outer_y:.1f}" class="uv-tick-mark"/>')
    return (
        '<svg class="uv-gauge" viewBox="0 0 240 205" role="img" aria-label="Đồng hồ chỉ số UV">'
        '<path d="M25 120 A95 95 0 0 1 215 120" fill="none" stroke="#E5E7EB" stroke-width="11" stroke-linecap="round"/>'
        f'<path class="uv-progress" d="M25 120 A95 95 0 0 1 215 120" fill="none" stroke="{color}" stroke-width="11" stroke-linecap="round" stroke-dasharray="{arc_length:.1f}" stroke-dashoffset="{dash_offset:.1f}"/>'
        f'{"".join(tick_marks)}'
        f'{"".join(ticks)}'
        f'<g class="uv-needle" style="transform:rotate({rotation:.1f}deg)"><path d="M120 120 L49 120" fill="none" stroke="{color}" stroke-width="5" stroke-linecap="round"/><circle cx="120" cy="120" r="7" fill="{color}"/><circle cx="120" cy="120" r="3" fill="#fff"/></g>'
        f'<text x="120" y="198" text-anchor="middle" class="uv-current">{displayed_value}</text>'
        '</svg>'
    )


def humidity_ring(value) -> str:
    circumference = 2 * math.pi * 43
    if value is None or pd.isna(value):
        percent_label = "—"
        ratio = 0.0
    else:
        ratio = min(100.0, max(0.0, float(value))) / 100.0
        percent_label = f"{float(value):.0f}%"
    dash_offset = circumference * (1 - ratio)
    svg = (
        '<svg viewBox="0 0 120 120" role="img" aria-label="Độ ẩm">'
        '<circle cx="60" cy="60" r="55" fill="#fff"/>'
        f'<circle cx="60" cy="60" r="43" fill="none" stroke="#edf0f0" stroke-width="8"/>'
        f'<circle cx="60" cy="60" r="43" fill="none" stroke="#83b56d" stroke-width="8" stroke-linecap="round" stroke-dasharray="{circumference:.1f}" stroke-dashoffset="{dash_offset:.1f}" transform="rotate(-90 60 60)"/>'
        '</svg>'
    )
    return f'<div class="humidity-ring">{svg}<span class="humidity-percent">{percent_label}</span></div>'


def aqi_scale_for(standard: str) -> tuple[int, ...]:
    return (0, 50, 100, 150, 200, 300, 500) if standard == "US AQI" else (0, 20, 40, 60, 80, 100, 200)


def aqi_scale_position(value: float, boundaries: tuple[int, ...]) -> float:
    if value <= boundaries[0]:
        return 0.0
    segment_count = len(boundaries) - 1
    for index in range(segment_count):
        lower, upper = boundaries[index], boundaries[index + 1]
        if value <= upper:
            fraction = (value - lower) / max(upper - lower, 1)
            return (index + fraction) / segment_count * 100
    return 100.0


def aqi_meter_markup(value, color: str, standard: str) -> str:
    boundaries = aqi_scale_for(standard)
    missing = value is None or pd.isna(value)
    numeric = 0.0 if missing else max(0.0, float(value))
    progress = 0.0 if missing else aqi_scale_position(numeric, boundaries)
    ticks = "".join(
        f'<span class="aqi-meter-tick" style="left:{index / (len(boundaries) - 1) * 100:.2f}%"></span>'
        for index in range(1, len(boundaries) - 1)
    )
    labels = "".join(
        f'<span style="left:{index / (len(boundaries) - 1) * 100:.2f}%">{bound:g}</span>'
        for index, bound in enumerate(boundaries)
    )
    max_value = boundaries[-1]
    current_value = 0 if missing else numeric
    return (
        f'<div class="aqi-meter-wrap"><div class="aqi-meter" role="progressbar" aria-label="AQI theo các ngưỡng phân loại" aria-valuemin="0" aria-valuemax="{max_value}" aria-valuenow="{current_value:g}">'
        f'<div class="aqi-meter-fill" style="width:{progress:.2f}%;background-color:{color}"></div>{ticks}</div>'
        f'<div class="aqi-scale" aria-hidden="true">{labels}</div></div>'
    )


def pm25_gauge_markup(value, standard: str) -> str:
    """Render measured PM2.5 concentration and its concentration guidance bands."""
    maximum = 500 if standard == "US AQI" else 140
    boundaries = [0.0]
    boundaries.extend(ceiling for ceiling, _label, _color in PM25_CONCENTRATION_BANDS[standard] if math.isfinite(ceiling) and ceiling < maximum)
    boundaries.append(float(maximum))
    missing = value is None or pd.isna(value)
    numeric = 0.0 if missing else max(0.0, float(value))
    ratio = min(numeric / maximum, 1.0)
    label, color = pm25_category(None if missing else numeric, standard)

    cx, cy, radius = 120.0, 98.0, 78.0
    circumference = 2 * math.pi * radius * 0.75
    dash_offset = circumference * (1 - ratio)
    start_x = cx + radius * math.cos(math.radians(135))
    start_y = cy + radius * math.sin(math.radians(135))
    end_x = cx + radius * math.cos(math.radians(45))
    end_y = cy + radius * math.sin(math.radians(45))
    arc_path = f"M{start_x:.1f} {start_y:.1f} A{radius:g} {radius:g} 0 1 1 {end_x:.1f} {end_y:.1f}"

    ticks = []
    labels = []
    for index, boundary in enumerate(boundaries):
        angle = math.radians(135 + (boundary / maximum) * 270)
        inner, outer = radius - 4, radius + 4
        x1, y1 = cx + inner * math.cos(angle), cy + inner * math.sin(angle)
        x2, y2 = cx + outer * math.cos(angle), cy + outer * math.sin(angle)
        lx, ly = cx + (radius + 15) * math.cos(angle), cy + (radius + 15) * math.sin(angle)
        ticks.append(f'<line class="pm25-tick" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
        if index in (0, len(boundaries) - 1):
            labels.append(f'<text class="pm25-tick-label" x="{lx:.1f}" y="{ly + 3:.1f}" text-anchor="middle">{boundary:g}</text>')

    needle_angle = math.radians(135 + ratio * 270)
    needle_x = cx + 48 * math.cos(needle_angle)
    needle_y = cy + 48 * math.sin(needle_angle)
    value_label = "—" if missing else f"{numeric:.1f}"
    status_label = "—" if missing else label
    aria_value = "không khả dụng" if missing else f"{numeric:.1f} µg/m³"
    return (
        f'<svg class="pm25-dial" viewBox="0 0 240 204" role="img" aria-label="PM2.5: {aria_value}, {status_label}">'
        f'<path class="pm25-track" d="{arc_path}"/>'
        f'<path class="pm25-progress" d="{arc_path}" stroke="{color}" stroke-dasharray="{circumference:.1f}" stroke-dashoffset="{dash_offset:.1f}"/>'
        f'{"".join(ticks)}{"".join(labels)}'
        f'<text class="pm25-state" x="120" y="45" text-anchor="middle" fill="{color}">{status_label}</text>'
        f'<line class="pm25-needle" x1="{cx:.1f}" y1="{cy:.1f}" x2="{needle_x:.1f}" y2="{needle_y:.1f}" stroke="{color}"/>'
        f'<circle class="pm25-hub" cx="{cx:.1f}" cy="{cy:.1f}" r="5.5" fill="{color}"/>'
        f'<text class="pm25-value" x="120" y="179" text-anchor="middle">{value_label}</text>'
        '<text class="pm25-unit" x="120" y="196" text-anchor="middle">µg/m³</text>'
        '</svg>'
    )


def card_markup(label: str, value: str, footer: str = "", standard: str = "US AQI") -> str:
    icon_svgs = {
        "Độ ẩm": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M12 3C9 7 5.5 10.5 5.5 14a6.5 6.5 0 0 0 13 0C18.5 10.5 15 7 12 3Z"/><path d="M9 15.5a3 3 0 0 0 3 3"/></svg>',
        "Tầm nhìn": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6Z"/><circle cx="12" cy="12" r="2.7"/></svg>',
        "Chất lượng không khí": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="M4 8h10a2 2 0 1 0-2-2M3 12h15a2 2 0 1 1-2 2M5 16h8"/></svg>',
    }
    icon = f'<span class="metric-label-icon" aria-hidden="true">{icon_svgs[label]}</span>' if label in icon_svgs else ""
    help_button = air_info_button("aqi", standard) if label == "Chất lượng không khí" else ""
    label_markup = f'<div class="metric-label">{icon}{label}</div>'
    if label == "Tầm nhìn":
        vision_src = weather_icon_data("vision.png")
        return f'<div class="metric-card">{label_markup}<div class="visibility-value-row"><img class="visibility-icon" src="{vision_src}" alt="Biểu tượng tầm nhìn"><div class="metric-value">{value}</div></div><div class="metric-foot"><strong>{footer}</strong></div></div>'
    if label == "Chỉ số UV":
        gauge_value = pd.to_numeric(value, errors="coerce")
        return f'<div class="metric-card uv-card">{label_markup}<div class="uv-main">{uv_gauge(gauge_value, value)}</div><div class="metric-foot">{footer}</div></div>'
    if label == "Tốc độ gió":
        direction_label = footer.removeprefix("Hướng ")
        compass_src = weather_icon_data("compass.png")
        compass = f'<span class="wind-compass" aria-hidden="true"><img src="{compass_src}" alt=""></span>'
        return f'<div class="metric-card wind-card">{label_markup}<div class="metric-value">{value}</div><div class="wind-direction">{compass}<span>{direction_label}</span></div></div>'
    if label == "Sun":
        sunrise_time, sunset_time = value.split("<small>/</small>")
        sun_rows = f'<div class="sun-times"><div class="sun-time"><span class="sun-arrow up" aria-hidden="true">↑</span><strong>{sunrise_time.strip()}</strong><span>Bình minh</span></div><div class="sun-time"><span class="sun-arrow down" aria-hidden="true">↓</span><strong>{sunset_time.strip()}</strong><span>Hoàng hôn</span></div></div>'
        return f'<div class="metric-card sunrise-card">{label_markup}{sun_rows}<div class="metric-foot">{footer}</div></div>'
    if label == "Độ ẩm":
        humidity = pd.to_numeric(value, errors="coerce")
        ring = humidity_ring(humidity)
        return f'<div class="metric-card humidity-card">{label_markup}{ring}<div class="metric-foot"><strong>{footer}</strong></div></div>'
    if label == "Chất lượng không khí":
        aqi_value = pd.to_numeric(value, errors="coerce")
        status, color = category(aqi_value, standard)
        meter = aqi_meter_markup(aqi_value, color, standard)
        return f'<div class="metric-card air-quality-card">{label_markup}<div class="metric-value">{value}</div>{meter}<div class="metric-foot"><strong style="color:{color}">{status}</strong></div></div>'
    if label in ("Độ ẩm", "Tầm nhìn", "Chất lượng không khí"):
        return f'<div class="metric-card">{label_markup}<div class="metric-value">{value}</div><div class="metric-foot"><strong>{footer}</strong></div></div>'
    return f'<div class="metric-card">{label_markup}<div class="metric-value">{value}</div><div class="metric-foot">{footer}</div></div>'
