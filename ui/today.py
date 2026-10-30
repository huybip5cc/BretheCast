"""Daily decision-mode presentation for the Streamlit dashboard."""

from __future__ import annotations

import math
from datetime import time
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from activity_rules import ACTIVITIES, rank_windows, score_hour, window_reason
from decision_engine import HORIZONS, generate_explanations, predict_exceedance
from health import TARGET_GROUPS, recommendation

DEFAULT_START = time(6, 0)
DEFAULT_END = time(22, 0)
DEFAULT_DURATION = 60


def current_preferences() -> dict[str, Any]:
    """Read the state from the previous rerun so the sidebar summary stays in sync."""
    return {
        "activity": st.session_state.get("suggest_activity", ACTIVITIES[0]),
        "group": st.session_state.get("suggest_group", TARGET_GROUPS[0]),
        "start": st.session_state.get("suggest_start", DEFAULT_START),
        "end": st.session_state.get("suggest_end", DEFAULT_END),
        "duration": st.session_state.get("suggest_duration", DEFAULT_DURATION),
        "threshold": st.session_state.get("suggest_threshold", 100),
    }


def scored_forecast(forecast: pd.DataFrame, activity: str, group: str) -> pd.DataFrame:
    if forecast.empty:
        return forecast.copy()
    rows = []
    for _, row in forecast.iterrows():
        score = score_hour(row, activity, group)
        rows.append({"risk_score": score["risk_score"], "risk_status": score["status"], "risk_components": score["components"]})
    return pd.concat([forecast.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def sidebar_conclusion(city: str, forecast: pd.DataFrame, plan: list[dict[str, Any]], activity: str, group: str) -> None:
    if plan:
        chosen = plan[0]
        label = "Nên tránh" if chosen["status"] == "avoid" else "Nên cân nhắc" if chosen["status"] == "caution" else "Khung giờ phù hợp"
        date_time = f"{chosen['start']:%H:%M}–{chosen['end']:%H:%M}"
        reasons = window_reason(chosen, forecast)
        explanation = " · ".join(reasons[:2]) if reasons else "Các yếu tố có dự báo trong khung này thuận lợi hơn những khung đã xếp hạng."
        st.markdown(
            f'<div class="today-sidebar-summary"><div class="today-kicker">{activity}</div>'
            f'<div class="today-sidebar-title">{label}<br>{date_time}</div>'
            f'<div class="today-sidebar-copy">{explanation}</div>'
            f'<div class="today-sidebar-copy" style="margin-top:10px">{recommendation(_max_aqi(chosen), group, "US AQI")}</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="today-sidebar-summary"><div class="today-kicker">Gợi ý hôm nay</div>'
            '<div class="today-sidebar-title">Chưa thể xếp hạng khung giờ</div>'
            '<div class="today-sidebar-copy">Cần dự báo AQI theo giờ liên tục để so sánh các khoảng rảnh.</div></div>',
            unsafe_allow_html=True,
        )
    st.markdown('<div class="side-divider"></div>', unsafe_allow_html=True)
    city_tile = st.session_state.get("selected_city_label", city)
    st.markdown(f'<div class="today-city-label">{city_tile}</div>', unsafe_allow_html=True)


def _max_aqi(window: dict[str, Any]) -> float | None:
    values = pd.to_numeric(pd.Series([row.get("us_aqi") for row in window.get("rows", [])]), errors="coerce").dropna()
    return float(values.max()) if not values.empty else None


def _window_card(window: dict[str, Any], number: int, forecast: pd.DataFrame) -> str:
    title = "Khung tốt nhất" if number == 0 else f"Phương án {number}"
    status = {"good": "Thuận lợi", "caution": "Cân nhắc", "avoid": "Nên tránh"}.get(window["status"], "")
    color = {"good": "#24996b", "caution": "#b1820d", "avoid": "#c45d50"}.get(window["status"], "#66717a")
    rows = pd.DataFrame(window.get("rows", []))
    metrics = []
    aqi_values = pd.to_numeric(rows.get("us_aqi", pd.Series(dtype="float64")), errors="coerce").dropna()
    if aqi_values.empty:
        aqi_values = pd.to_numeric(rows.get("us_aqi_pm2_5", pd.Series(dtype="float64")), errors="coerce").dropna()
    if not aqi_values.empty:
        leaf = '<svg class="window-mini-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 3C10 3 4 7 4 14c0 3 2 5 5 5 7 0 11-6 11-16Z" fill="#31a875"/><path d="M4 21c4-6 8-9 13-13" fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/></svg>'
        metrics.append(f'<span class="window-reason-item">AQI dự báo cao nhất <b>{aqi_values.max():.0f}</b>{leaf}</span>')
    uv_values = pd.to_numeric(rows.get("uv_index", pd.Series(dtype="float64")), errors="coerce").dropna()
    if not uv_values.empty:
        sun = '<span class="window-mini-icon" aria-hidden="true">☀️</span>'
        metrics.append(f'<span class="window-reason-item">UV cao nhất <b>{uv_values.max():.0f}</b>{sun}</span>')
    reason = "".join(metrics)
    card_class = "window-card-featured" if number == 0 else "window-card-alt"
    return (
        f'<div class="window-card {card_class}"><div class="window-card-copy">'
        f'<div class="today-kicker">{title}</div>'
        f'<div class="window-time">{window["start"]:%a %H:%M}–{window["end"]:%H:%M}</div>'
        f'<div class="window-status {window["status"]}" style="--status-color:{color};color:{color}">{status}</div>'
        f'<div class="window-reason">{reason}</div>'
        f'<div class="window-source">{window["source"]}</div></div></div>'
    )


def _timeline(forecast: pd.DataFrame, plan: list[dict[str, Any]]) -> None:
    st.markdown('<div class="section-title">Điều kiện trong 48 giờ tới</div>', unsafe_allow_html=True)
    if forecast.empty:
        st.markdown('<div class="chart-card">Dự báo theo giờ hiện chưa khả dụng.</div>', unsafe_allow_html=True)
        return
    custom = []
    for row in forecast.itertuples():
        aqi = getattr(row, "us_aqi", np_nan())
        source = getattr(row, "aqi_source", "") or "AQI theo giờ chưa có"
        status = {"good": "Thuận lợi", "caution": "Cân nhắc", "avoid": "Nên tránh", "unranked": "Chưa xếp hạng"}.get(row.risk_status, "")
        custom.append([source, status, aqi])
    scores = pd.to_numeric(forecast.risk_score, errors="coerce")
    segments = 12
    segment_height = scores / segments
    bottom = (222, 241, 251)
    top = (91, 164, 218)
    fig = go.Figure()
    for index in range(segments):
        ratio = index / (segments - 1)
        red, green, blue = (round(bottom[channel] + (top[channel] - bottom[channel]) * ratio) for channel in range(3))
        alpha = 0.42 + 0.23 * ratio
        fig.add_trace(go.Bar(
            x=forecast.time, y=segment_height,
            marker=dict(color=f"rgba({red},{green},{blue},{alpha:.2f})", line=dict(width=0)),
            customdata=custom,
            hovertemplate="%{x|%a %d/%m %H:%M}<br>%{customdata[1]}<br>AQI %{customdata[2]:.0f}<br>%{customdata[0]}<extra></extra>",
            showlegend=False,
        ))
    if plan:
        fig.add_vrect(x0=plan[0]["start"], x1=plan[0]["end"], fillcolor="rgba(116,184,224,.08)", line=dict(color="#8bbfe0", width=0.8), layer="below")
    fig.update_layout(
        height=230, barmode="stack", bargap=0.28, margin=dict(l=8, r=8, t=8, b=28), paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Poppins, sans-serif", color="#7f8d97", size=10), showlegend=False,
        xaxis=dict(showgrid=False, showline=False, tickfont=dict(color="#82919a"), tickformat="%a %H:%M", nticks=12, title=None),
        yaxis=dict(showgrid=True, gridcolor="rgba(105,161,195,.14)", gridwidth=0.7, zeroline=False, showline=False, range=[0, 100], title="Điều kiện · tốt → kém"),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.markdown('<div class="source-note">Chiều cao cột thể hiện mức điều kiện tổng hợp; vùng xanh nhạt đánh dấu khung được chọn. Giờ không có AQI được để trống.</div>', unsafe_allow_html=True)


def np_nan() -> float:
    return float("nan")


def _probability_cards(suite: dict[str, Any] | None, threshold: int) -> None:
    suite_data = suite if isinstance(suite, dict) else {}
    try:
        threshold = int(threshold)
    except (TypeError, ValueError, OverflowError):
        threshold = 100
    classification = suite_data.get("classification", {})
    if not isinstance(classification, dict):
        classification = {}
    threshold_models = classification.get(threshold, classification.get(str(threshold), {}))
    if not isinstance(threshold_models, dict):
        threshold_models = {}
    cards = []
    for horizon in HORIZONS:
        result = threshold_models.get(horizon, threshold_models.get(str(horizon), {}))
        if not isinstance(result, dict):
            result = {}
        probability = predict_exceedance(result, suite_data.get("latest"))
        try:
            probability = float(probability) if probability is not None else None
            if probability is not None and (not math.isfinite(probability) or not 0 <= probability <= 1):
                probability = None
        except (TypeError, ValueError, OverflowError):
            probability = None
        if probability is None:
            amount = "—"
            sub = "Chuỗi CAMS chưa đủ để kiểm định xác suất theo thời gian."
        else:
            amount = f"{probability:.0%}"
            metrics = result.get("metrics", {})
            if not isinstance(metrics, dict):
                metrics = {}
            baseline_data = result.get("climatology", {})
            if not isinstance(baseline_data, dict):
                baseline_data = {}
            baseline = baseline_data.get("brier")
            brier = metrics.get("brier")
            comparison = pd.to_numeric(pd.Series([brier, baseline]), errors="coerce")
            if comparison.notna().all():
                sub = "Sai số thấp hơn tỉ lệ nền" if float(comparison.iloc[0]) < float(comparison.iloc[1]) else "Chưa tốt hơn tỉ lệ nền"
            else:
                sub = "Đã hiệu chỉnh theo một giai đoạn thời gian riêng"
        cards.append(
            f'<div class="probability-card"><div class="today-kicker">{horizon} giờ tới · AQI &gt; {threshold}</div>'
            f'<div class="probability-value">{amount}</div><div class="probability-copy">{sub}</div></div>'
        )
    st.markdown('<div class="section-title">Khả năng AQI vượt ngưỡng</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="probability-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def _weather_card(plan: list[dict[str, Any]]) -> None:
    if not plan:
        st.markdown(
            '<div class="today-mini-card"><div class="metric-label">Thời tiết trong khung được chọn</div>'
            '<div class="today-mini-copy">Chưa có khung giờ để tổng hợp điều kiện.</div></div>',
            unsafe_allow_html=True,
        )
        return
    rows = pd.DataFrame(plan[0]["rows"])
    def values(name: str) -> pd.Series:
        source = rows[name] if name in rows else pd.Series(np_nan(), index=rows.index)
        return pd.to_numeric(source, errors="coerce")
    temp = values("temperature_2m")
    uv = values("uv_index")
    rain = values("precipitation_probability")
    parts = []
    if temp.notna().any():
        parts.append(f"Nhiệt độ {temp.min():.0f}–{temp.max():.0f}°C")
    if uv.notna().any():
        parts.append(f"UV cao nhất {uv.max():.0f}")
    if rain.notna().any():
        parts.append(f"Mưa tối đa {rain.max():.0f}%")
    text = " · ".join(parts) or "Thời tiết theo giờ chưa có đủ chỉ số để tóm tắt."
    st.markdown(
        '<div class="today-mini-card"><div class="metric-label">Thời tiết trong khung được chọn</div>'
        f'<div class="today-mini-copy">{text}</div>'
        '<div class="window-source">Đối chiếu cùng dự báo AQI và nhóm đã chọn.</div></div>',
        unsafe_allow_html=True,
    )


def _why_card(suite: dict[str, Any] | None) -> None:
    sentences = ((suite or {}).get("explanation") or {}).get("sentences", [])
    if not sentences:
        sentences = ["Mô hình sẽ nêu các yếu tố có đóng góp rõ rệt khi chuỗi huấn luyện và kiểm tra đạt yêu cầu."]
    items = "".join(f"<li>{text}</li>" for text in sentences[:3])
    method = ((suite or {}).get("explanation") or {}).get("method", "")
    st.markdown(
        '<div class="today-mini-card"><div class="metric-label">Vì sao?</div>'
        f'<ul class="today-why-list">{items}</ul>'
        f'<div class="window-source">AQI sau 6 giờ · {method}</div></div>',
        unsafe_allow_html=True,
    )


def _calibration_chart(result: dict[str, Any]) -> None:
    points = result.get("calibration_points", [])
    if not points:
        st.caption("Đường hiệu chỉnh sẽ hiện khi tập kiểm tra có đủ cả hai kết quả AQI.")
        return
    observed, predicted = zip(*points)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color="#bfc1c6", dash="dash"), name="Hiệu chỉnh hoàn hảo"))
    fig.add_trace(go.Scatter(x=predicted, y=observed, mode="lines+markers", line=dict(color="#5362bf", width=2), marker=dict(size=7), name="Mô hình"))
    fig.update_layout(
        height=230, margin=dict(l=8, r=8, t=4, b=20), paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Poppins, sans-serif", color="#7e8187", size=10), showlegend=True,
        xaxis=dict(title="Xác suất dự báo", range=[0, 1], gridcolor="#f0f0f2"),
        yaxis=dict(title="Tần suất quan sát", range=[0, 1], gridcolor="#f0f0f2"),
    )
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _reliability(suite: dict[str, Any] | None, threshold: int) -> None:
    st.markdown('<div class="source-note">Kiểm tra theo thời gian: 60% đầu để huấn luyện, giai đoạn kế tiếp để hiệu chỉnh xác suất, 20% cuối để đánh giá; giữa các phần bỏ cách ít nhất bằng chân trời dự báo. Mô hình AQI/PM₂.₅ đầu vào là CAMS hồi cứu, không phải trạm đo.</div>', unsafe_allow_html=True)
    if not suite:
        st.info("Mô hình chưa được đánh giá vì dữ liệu AQI hoặc thời tiết theo giờ hiện chưa sẵn sàng.")
        return
    rows = []
    for horizon in HORIZONS:
        result = suite.get("classification", {}).get(threshold, {}).get(horizon, {})
        metrics = result.get("metrics", {})
        baseline = result.get("climatology", {})
        persistence = result.get("current_over_threshold", {})
        rows.append({
            "Chân trời": f"{horizon} giờ",
            "Giờ kiểm tra": result.get("test_n", 0),
            "Brier · mô hình": _fmt_metric(metrics.get("brier")),
            "Brier · tỉ lệ nền": _fmt_metric(baseline.get("brier")),
            "ROC-AUC": _fmt_metric(metrics.get("roc_auc")),
            "PR-AUC": _fmt_metric(metrics.get("pr_auc")),
            "Brier · AQI đang vượt": _fmt_metric(persistence.get("brier")),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Cảnh báo dùng xác suất ≥25% theo giả định bỏ sót một đợt vượt ngưỡng tốn kém gấp 3 lần một cảnh báo nhầm. Đây là lựa chọn vận hành minh bạch, không phải ngưỡng y tế.")
    chart_result = suite.get("classification", {}).get(threshold, {}).get(6, {})
    st.markdown('<div class="section-note">Hiệu chỉnh xác suất · 6 giờ</div>', unsafe_allow_html=True)
    _calibration_chart(chart_result)

    reg_rows = []
    for horizon, result in suite.get("regression", {}).items():
        reg_rows.append({
            "Chân trời": f"{horizon} giờ",
            "MAE · mô hình": _fmt_metric(result.get("mae")),
            "MAE · giữ AQI hiện tại": _fmt_metric(result.get("persistence_mae")),
            "Giờ kiểm tra": result.get("test_n", 0),
        })
    st.markdown('<div class="section-note">Sai số dự báo AQI · so với giữ nguyên AQI giờ trước</div>', unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(reg_rows), hide_index=True, width="stretch")
    ablation = suite.get("ablation", {})
    if ablation.get("status") == "ready":
        full = suite.get("regression", {}).get(6, {})
        st.caption(f"Ablation 6 giờ: MAE dùng đủ biến {full.get('mae', float('nan')):.1f}; chỉ dùng AQI trễ {ablation.get('mae', float('nan')):.1f}.")

    explanation = suite.get("explanation") or {}
    contributions = explanation.get("contributions", {})
    if contributions:
        names = sorted(contributions, key=lambda name: abs(contributions[name]))[-10:]
        values = [contributions[name] for name in names]
        labels = [name.replace("_", " ") for name in names]
        fig = go.Figure(go.Bar(x=values, y=labels, orientation="h", marker_color=["#c87955" if value > 0 else "#6e9b82" for value in values], hovertemplate="%{y}<br>Đóng góp cục bộ %{x:+.1f} điểm AQI<extra></extra>"))
        fig.update_layout(height=max(200, 24 * len(names)), margin=dict(l=8, r=8, t=4, b=18), paper_bgcolor="white", plot_bgcolor="white", font=dict(family="Poppins, sans-serif", color="#7e8187", size=10), xaxis=dict(title="AQI so với mức tham chiếu", zeroline=True, zerolinecolor="#d9dade", gridcolor="#f0f0f2"), yaxis=dict(title=None, showgrid=False))
        st.markdown(f'<div class="section-note">Giải thích · {explanation.get("method", "")}</div>', unsafe_allow_html=True)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _fmt_metric(value: Any) -> str:
    try:
        return f"{float(value):.3f}" if math.isfinite(float(value)) else "—"
    except (TypeError, ValueError):
        return "—"


def render_today_dashboard(
    suite: dict[str, Any] | None,
    forecast: pd.DataFrame,
    standard: str = "US AQI",
) -> list[dict[str, Any]]:
    """Render the third mode and return ranked windows for the sidebar summary."""
    with st.container(key="today-planner-form"):
        st.markdown('<div class="section-title" style="margin-top:0">Gợi ý hôm nay 📅</div><div class="section-note">Chọn hoạt động và khoảng rảnh để tìm giờ thuận lợi hơn trong 48 giờ tới.</div>', unsafe_allow_html=True)
        activity_col, group_col, start_col, end_col, duration_col = st.columns([1.25, 1.4, 0.8, 0.8, 0.85], gap="small")
        with activity_col:
            activity = st.selectbox("Hoạt động", ACTIVITIES, key="suggest_activity")
        with group_col:
            group = st.selectbox("Nhóm đối tượng", TARGET_GROUPS, key="suggest_group")
        with start_col:
            start = st.time_input("Rảnh từ", value=DEFAULT_START, key="suggest_start")
        with end_col:
            end = st.time_input("Đến", value=DEFAULT_END, key="suggest_end")
        with duration_col:
            duration = st.select_slider("Thời lượng", options=(30, 60, 90, 120), value=DEFAULT_DURATION, format_func=lambda value: f"{value} phút", key="suggest_duration")
        threshold = st.selectbox("Ngưỡng cảnh báo", (100, 150), format_func=lambda value: f"US AQI &gt; {value}", key="suggest_threshold")

    scored = scored_forecast(forecast, activity, group)
    plan = rank_windows(scored, activity, group, start, end, int(duration), alternatives=2)
    st.markdown('<div class="section-title">Khung giờ tốt nhất 48 giờ tới</div>', unsafe_allow_html=True)
    if plan:
        st.markdown(_window_card(plan[0], 0, scored), unsafe_allow_html=True)
        if len(plan) > 1:
            st.markdown('<div class="section-note" style="margin-top:14px">Các lựa chọn khác, không chồng lấn</div>', unsafe_allow_html=True)
            cols = st.columns(len(plan) - 1, gap="small")
            for index, alternative in enumerate(plan[1:]):
                with cols[index]:
                    st.markdown(_window_card(alternative, index + 1, scored), unsafe_allow_html=True)
    else:
        st.markdown('<div class="chart-card">Chưa thể xếp hạng: cần các giờ AQI liên tiếp trong khoảng rảnh đã chọn.</div>', unsafe_allow_html=True)
    _timeline(scored, plan)

    _probability_cards(suite, int(threshold))
    left, middle, right = st.columns(3, gap="small")
    with left:
        _why_card(suite)
    with middle:
        _weather_card(plan)
    with right:
        current_aqi = None
        if plan:
            current_aqi = _max_aqi(plan[0])
        advice = recommendation(current_aqi, group, "US AQI")
        advice_copy = advice if advice != "—" else "Lời khuyên sẽ xuất hiện khi có AQI trong khung được chọn."
        st.markdown(
            '<div class="today-mini-card"><div class="metric-label">Nhóm đã chọn</div>'
            f'<div class="today-mini-copy">{advice_copy}</div>'
            '<div class="window-source">Hướng dẫn chung theo US AQI; nhóm không làm thay đổi ngưỡng.</div></div>',
            unsafe_allow_html=True,
        )
    with st.expander("Độ tin cậy của mô hình", expanded=False):
        _reliability(suite, int(threshold))
    st.markdown('<div class="source-note" style="margin-top:18px">Gợi ý tham khảo, không thay thế tư vấn y tế. Dữ liệu AQI/PM₂.₅ do CAMS mô hình hóa; dự báo giờ ưu tiên Open-Meteo, giờ được project bổ sung bằng ML được ghi nhãn riêng.</div>', unsafe_allow_html=True)
    return plan
