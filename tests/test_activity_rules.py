from datetime import time

import pandas as pd
import pytest

from activity_rules import ACTIVITIES, ACTIVITY_WEIGHTS, format_uv_index, rank_windows, score_hour


def test_activity_menu_has_flexible_options_and_matching_weights():
    expected = {
        "Đi bộ / chạy bộ ngoài trời",
        "Đạp xe ngoài trời",
        "Tập thể dục ngoài trời",
        "Đi dạo / vui chơi công viên",
        "Dã ngoại",
        "Làm vườn / chăm sóc cây",
        "Đi chợ / mua sắm linh hoạt",
        "Phơi quần áo",
        "Mở cửa thông thoáng nhà",
    }

    assert set(ACTIVITIES) == expected
    assert not {"Đón con", "Đi làm, di chuyển"} & set(ACTIVITIES)
    assert set(ACTIVITY_WEIGHTS) == set(ACTIVITIES)
    assert all(sum(weights.values()) == pytest.approx(1) for weights in ACTIVITY_WEIGHTS.values())


def test_every_activity_can_be_scored():
    conditions = {
        "us_aqi": 65,
        "temperature_2m": 25,
        "relative_humidity_2m": 55,
        "uv_index": 3,
        "precipitation_probability": 10,
        "precipitation": 0,
    }

    for activity in ACTIVITIES:
        result = score_hour(conditions, activity)
        assert 0 <= result["risk_score"] <= 100


def test_small_uv_values_are_not_rounded_to_zero():
    assert format_uv_index(0) == "<1"
    assert format_uv_index(0.4) == "<1"
    assert format_uv_index(1) == "1.0"
    assert format_uv_index(5.7) == "5.7"


def test_hour_score_uses_health_bands_and_does_not_invent_group_cutoffs():
    conditions = {
        "us_aqi": 155,
        "us_aqi_pm2_5": 142,
        "temperature_2m": 28,
        "relative_humidity_2m": 60,
        "uv_index": 5,
        "precipitation_probability": 20,
        "precipitation": 0,
    }
    ordinary = score_hour(conditions, ACTIVITIES[0], "Người đi làm / sinh hoạt thông thường")
    sensitive = score_hour(conditions, ACTIVITIES[0], "Trẻ nhỏ")

    assert ordinary["risk_score"] == sensitive["risk_score"]
    assert ordinary["status"] in {"good", "caution", "avoid"}
    assert ordinary["components"]["air"] >= 60


def test_hours_without_aqi_cannot_be_ranked():
    result = score_hour({"temperature_2m": 25, "uv_index": 1}, ACTIVITIES[0])

    assert pd.isna(result["risk_score"])
    assert result["status"] == "unranked"


def test_window_ranking_minimizes_worst_hour_before_mean():
    times = pd.date_range("2026-01-01 06:00", periods=6, freq="h")
    frame = pd.DataFrame({
        "time": times,
        # First two-hour window has a better mean but one sharply worse hour.
        "us_aqi": [40, 190, 70, 70, 85, 85],
        "us_aqi_pm2_5": [35, 180, 65, 65, 80, 80],
        "temperature_2m": [25] * 6,
        "relative_humidity_2m": [50] * 6,
        "uv_index": [1] * 6,
        "precipitation_probability": [0] * 6,
        "precipitation": [0] * 6,
        "aqi_source": ["Dự báo Open-Meteo"] * 6,
    })

    ranked = rank_windows(frame, ACTIVITIES[0], "Người đi làm / sinh hoạt thông thường", time(6), time(12), 120)

    assert ranked
    assert ranked[0]["start"] == pd.Timestamp("2026-01-01 08:00")
    assert ranked[0]["worst_score"] < ranked[1]["worst_score"]
    assert ranked[0]["end"] == pd.Timestamp("2026-01-01 10:00")
