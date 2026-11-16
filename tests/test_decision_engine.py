import pandas as pd

from decision_engine import _split


def test_chronological_split_purges_future_horizon():
    samples = pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=240, freq="h"),
        "target": range(240),
    })
    train, test = _split(samples, horizon=12, test_fraction=0.2)

    assert not train.empty and not test.empty
    assert train.time.max() <= test.time.min() - pd.Timedelta(hours=12)
    assert train.time.max() < test.time.min()
