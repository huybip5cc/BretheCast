import pandas as pd

from decision_engine import chronological_split, generate_explanations


def test_chronological_split_purges_future_horizon():
    samples = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=240, freq="h"),
        "target": range(240),
    })
    train, test = chronological_split(samples, horizon_hours=12, test_fraction=0.2)

    assert not train.empty and not test.empty
    assert train.time.max() <= test.time.min() - pd.Timedelta(hours=12)
    assert train.time.max() < test.time.min()


def test_explanations_are_short_cautious_and_use_real_contributions():
    current = pd.Series({"us_aqi_lag_1h": 124.0, "uv_index": 7.0})
    sentences = generate_explanations({"us_aqi_lag_1h": 18.0, "uv_index": -3.5}, current)

    assert len(sentences) == 2
    assert "theo mô hình" in sentences[0]
    assert "AQI giờ trước" in sentences[0]
    assert "18 điểm" in sentences[0]
