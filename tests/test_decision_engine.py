import numpy as np
import pandas as pd
import pytest

from decision_engine import (
    FEATURES,
    _fit_classifier,
    _split,
    _supervised_feature_table,
    build_feature_frame,
    explain_probability,
    predict_exceedance,
)


def _historical_inputs(periods: int = 36) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build deterministic hourly weather and air data safely before the current time."""
    end = pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").tz_localize(None).floor("h") - pd.Timedelta(hours=1)
    times = pd.date_range(end=end, periods=periods, freq="h")
    values = np.arange(periods, dtype=float)
    weather = pd.DataFrame({
        "time": times,
        "temperature_2m": 20 + values,
        "relative_humidity_2m": 50 + values,
        "wind_speed_10m": values,
        "precipitation": np.ones(periods),
        "surface_pressure": 1000 + 2 * values,
    })
    air = pd.DataFrame({"time": times, "us_aqi": 40 + values, "pm2_5": 5 + values})
    return weather, air


def _feature_rows(aqi: list[float], forecast: list[bool] | None = None) -> pd.DataFrame:
    """Build complete feature rows for testing future targets."""
    rows = pd.DataFrame({name: np.ones(len(aqi), dtype=float) for name in FEATURES})
    rows["us_aqi_now"] = aqi
    rows["time"] = pd.date_range("2026-01-01", periods=len(aqi), freq="h")
    rows["is_forecast"] = forecast or [False] * len(aqi)
    return rows


def _classifier_data(periods: int = 300, positive_only: bool = False) -> pd.DataFrame:
    """Build enough complete rows to exercise the time split and classifier."""
    index = np.arange(periods)
    target = np.full(periods, 120.0) if positive_only else np.where(index % 2, 120.0, 80.0)
    data = pd.DataFrame({
        feature: index * 0.01 + column_index
        for column_index, feature in enumerate(FEATURES)
    })
    data["us_aqi_now"] = target
    data["time"] = pd.date_range("2026-01-01", periods=periods, freq="h")
    data["target"] = target
    return data


def test_chronological_split_purges_future_horizon():
    samples = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=240, freq="h"),
        "target": range(240),
    })
    train, test = _split(samples, horizon=12, test_fraction=0.2)

    assert not train.empty and not test.empty
    assert train.time.max() <= test.time.min() - pd.Timedelta(hours=12)
    assert train.time.max() < test.time.min()


def test_build_feature_frame_calculates_hourly_and_rolling_features():
    weather, air = _historical_inputs()

    frame = build_feature_frame(weather, air)

    assert len(frame) == len(weather)
    assert frame.time.is_monotonic_increasing
    assert set(["time", *FEATURES, "is_forecast"]).issubset(frame.columns)
    assert not frame.is_forecast.any()
    assert frame.loc[1, "us_aqi_change_1h"] == pytest.approx(1)
    assert frame.loc[3, "us_aqi_change_3h"] == pytest.approx(3)
    assert frame.loc[3, "wind_mean_6h"] == pytest.approx(1.5)
    assert frame.loc[3, "pressure_change_3h"] == pytest.approx(6)
    assert frame.loc[15, "us_aqi_mean_24h"] == pytest.approx(47.5)
    assert frame.loc[15, "us_aqi_max_24h"] == pytest.approx(55)
    assert frame.loc[17, "precipitation_sum_24h"] == pytest.approx(18)

    hour = frame.loc[0, "time"].hour
    assert frame.loc[0, "hour_sin"] == pytest.approx(np.sin(2 * np.pi * hour / 24))
    assert frame.loc[0, "hour_cos"] == pytest.approx(np.cos(2 * np.pi * hour / 24))


def test_build_feature_frame_keeps_last_duplicate_and_does_not_fill_missing_hours():
    weather, air = _historical_inputs(8)
    missing_time = weather.loc[3, "time"]
    weather = weather.drop(index=3)
    air = air.drop(index=3)
    duplicate_weather = pd.DataFrame([{
        **weather.iloc[0].to_dict(), "temperature_2m": 99.0,
    }])
    duplicate_air = pd.DataFrame([{
        **air.iloc[0].to_dict(), "us_aqi": 99.0,
    }])
    weather = pd.concat([weather, duplicate_weather], ignore_index=True)
    air = pd.concat([air, duplicate_air], ignore_index=True)

    frame = build_feature_frame(weather, air).set_index("time")

    assert len(frame) == 8
    assert frame.loc[weather.iloc[0]["time"], "temperature_2m"] == pytest.approx(99)
    assert frame.loc[air.iloc[0]["time"], "us_aqi_now"] == pytest.approx(99)
    assert pd.isna(frame.loc[missing_time, "temperature_2m"])
    assert pd.isna(frame.loc[missing_time, "us_aqi_now"])


def test_build_feature_frame_empty_inputs_returns_expected_columns():
    frame = build_feature_frame(pd.DataFrame(), pd.DataFrame())

    assert frame.empty
    assert list(frame.columns) == ["time", *FEATURES, "is_forecast"]


def test_supervised_feature_table_uses_only_the_next_horizon_and_historical_rows():
    features = _feature_rows([10, 50, 20, 80, 30, 40], [False, False, False, False, False, True])

    table = _supervised_feature_table(features, horizon=2)

    assert table.target.tolist() == [50, 80, 80]
    assert not table.is_forecast.any()
    assert table.time.tolist() == features.time.iloc[:3].tolist()


def test_supervised_feature_table_drops_missing_features_and_future_targets():
    features = _feature_rows([20, 30, 40, 50, 60, 70])
    features.loc[1, "temperature_2m"] = np.nan

    table = _supervised_feature_table(features, horizon=2)

    assert table.time.tolist() == features.time.iloc[[0, 2, 3]].tolist()
    assert table["temperature_2m"].notna().all()
    assert table.target.notna().all()


def test_supervised_feature_table_empty_input_adds_target_column():
    features = pd.DataFrame(columns=["time", *FEATURES, "is_forecast"])

    table = _supervised_feature_table(features, horizon=6)

    assert table.empty
    assert "target" in table.columns


def test_fit_classifier_trains_and_reports_metrics_with_both_classes():
    result = _fit_classifier(_classifier_data(), horizon=6, threshold=100)

    assert result["status"] == "ready"
    assert result["train_n"] >= 100
    assert result["test_n"] >= 30
    assert result["features"] == list(FEATURES)
    assert 0 <= result["metrics"]["brier"] <= 1
    assert 0 <= result["metrics"]["roc_auc"] <= 1
    assert 0 <= result["metrics"]["pr_auc"] <= 1
    assert len(result["test_probabilities"]) == result["test_n"]


def test_fit_classifier_labels_only_values_above_threshold_as_exceedances():
    data = _classifier_data()
    data["target"] = np.where(np.arange(len(data)) % 2, 101.0, 100.0)

    result = _fit_classifier(data, horizon=6, threshold=100)

    assert result["status"] == "ready"
    assert set(result["test_labels"]) == {0, 1}


@pytest.mark.parametrize("target", [80.0, 120.0])
def test_fit_classifier_returns_insufficient_when_training_has_one_class(target):
    data = _classifier_data(positive_only=True)
    data["target"] = target

    result = _fit_classifier(data, horizon=6, threshold=100)

    assert result["status"] == "insufficient"
    assert "model" not in result


def test_fit_classifier_returns_insufficient_when_sample_is_too_small():
    result = _fit_classifier(_classifier_data(periods=80), horizon=6, threshold=100)

    assert result["status"] == "insufficient"
    assert "model" not in result


class _FixedProbabilityModel:
    def predict_proba(self, rows):
        return np.array([[0.3, 0.7]])


def test_predict_exceedance_handles_unready_and_missing_features():
    result = {"status": "ready", "features": ["a", "b"], "model": _FixedProbabilityModel()}

    assert predict_exceedance({"status": "insufficient"}, pd.Series({"a": 1, "b": 2})) is None
    assert predict_exceedance(result, None) is None
    assert predict_exceedance(result, pd.Series({"a": 1, "b": np.nan})) is None
    assert predict_exceedance(result, pd.Series({"a": 1, "b": 2})) == pytest.approx(0.7)


def test_explain_probability_matches_model_probability_and_logit_decomposition():
    result = _fit_classifier(_classifier_data(), horizon=6, threshold=100)
    latest = _classifier_data().iloc[-1]

    explanation = explain_probability(result, latest)
    probability = predict_exceedance(result, latest)
    contributions = sum(row["contribution"] for row in explanation["rows"])

    assert explanation["logit"] == pytest.approx(explanation["intercept"] + contributions)
    assert explanation["probability"] == pytest.approx(probability)
    assert explanation["probability"] == pytest.approx(1 / (1 + np.exp(-explanation["logit"])))
    assert {row["feature"] for row in explanation["rows"]} == set(FEATURES)
