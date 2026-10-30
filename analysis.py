"""AQI categories, daily aggregation, historical summaries and anomaly checks."""

from __future__ import annotations

import pandas as pd

AQI_STANDARDS = {
    "US AQI": {
        "column": "us_aqi",
        "bands": ((50, "Tốt", "#5b9278"), (100, "Trung bình", "#b39343"), (150, "Không tốt cho nhóm nhạy cảm", "#c77d3d"), (200, "Không tốt", "#b75e58"), (300, "Rất không tốt", "#866893"), (float("inf"), "Nguy hại", "#6e343a")),
    },
    "EU AQI": {
        "column": "european_aqi",
        "bands": ((20, "Tốt", "#5b9278"), (40, "Khá", "#8a9a61"), (60, "Trung bình", "#b39343"), (80, "Kém", "#c77d3d"), (100, "Rất kém", "#b75e58"), (float("inf"), "Cực kém", "#6e343a")),
    },
}

# PM₂.₅ concentration bands (µg/m³). US EPA breakpoints are 24-hour
# concentration bands; EEA bands are hourly. The app's value is a modeled
# current concentration, so these are displayed as guidance bands, not as AQI.
PM25_CONCENTRATION_BANDS = {
    "US AQI": (
        (9.0, "Tốt", "#5b9278"),
        (35.4, "Trung bình", "#b39343"),
        (55.4, "Không tốt cho nhóm nhạy cảm", "#c77d3d"),
        (125.4, "Không tốt", "#b75e58"),
        (225.4, "Rất không tốt", "#866893"),
        (float("inf"), "Nguy hại", "#6e343a"),
    ),
    "EU AQI": (
        (5.0, "Tốt", "#5b9278"),
        (15.0, "Khá", "#8a9a61"),
        (50.0, "Trung bình", "#b39343"),
        (90.0, "Kém", "#c77d3d"),
        (140.0, "Rất kém", "#b75e58"),
        (float("inf"), "Cực kém", "#6e343a"),
    ),
}


def pm25_category(value: float | None, standard: str) -> tuple[str, str]:
    """Return a PM₂.₅ concentration band, independent of the AQI index value."""
    if value is None or pd.isna(value):
        return "—", "#9b9da1"
    for ceiling, label, color in PM25_CONCENTRATION_BANDS[standard]:
        if value <= ceiling:
            return label, color
    return "—", "#9b9da1"


def category(value: float | None, standard: str) -> tuple[str, str]:
    if value is None or pd.isna(value):
        return "—", "#9b9da1"
    for ceiling, label, color in AQI_STANDARDS[standard]["bands"]:
        if value <= ceiling:
            return label, color
    return "—", "#9b9da1"


def daily_aqi(frame: pd.DataFrame, standard: str, forecast: bool = False) -> pd.DataFrame:
    column = AQI_STANDARDS[standard]["column"]
    if frame.empty:
        return pd.DataFrame(columns=["date", "aqi", "pm2_5"])
    sample = frame.loc[frame.is_forecast == forecast] if "is_forecast" in frame else frame
    sample = sample.dropna(subset=[column])
    if sample.empty:
        return pd.DataFrame(columns=["date", "aqi", "pm2_5"])
    return (
        sample.groupby("date", as_index=False)
        .agg(aqi=(column, "mean"), pm2_5=("pm2_5", "mean"), peak=(column, "max"), hours=(column, "count"))
        .sort_values("date")
    )


def daily_aqi_range(frame: pd.DataFrame, standard: str) -> pd.DataFrame:
    """Summarize real hourly values by day and source; missing hours stay missing."""
    columns = ["date", "is_forecast", "minimum", "maximum", "mean", "hours"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    work = frame.copy()
    col = AQI_STANDARDS[standard]["column"]
    if "date" not in work:
        work["date"] = work["time"].dt.date
    if "is_forecast" not in work:
        work["is_forecast"] = False
    work = work.dropna(subset=[col])
    if work.empty:
        return pd.DataFrame(columns=columns)
    return (
        work.groupby(["date", "is_forecast"], as_index=False)
        .agg(minimum=(col, "min"), maximum=(col, "max"), mean=(col, "mean"), hours=(col, "count"))
        .sort_values(["date", "is_forecast"])
        .reset_index(drop=True)
    )


def hourly_aqi_pattern(
    frame: pd.DataFrame,
    standard: str,
    day_type: str,
    minimum_days: int = 3,
) -> tuple[pd.DataFrame, int] | None:
    """Return historical AQI means by clock hour and number of contributing dates."""
    if frame.empty:
        return None
    col = AQI_STANDARDS[standard]["column"]
    work = frame.loc[~frame["is_forecast"]].dropna(subset=[col]).copy() if "is_forecast" in frame else frame.dropna(subset=[col]).copy()
    if work.empty:
        return None
    work["date"] = work["time"].dt.date
    weekday = work["time"].dt.dayofweek < 5
    work = work.loc[weekday if day_type == "Ngày thường" else ~weekday]
    day_count = int(work["date"].nunique())
    if day_count < minimum_days:
        return None
    work["hour"] = work["time"].dt.hour
    hourly = (
        work.groupby("hour")
        .agg(aqi_mean=(col, "mean"), sample_days=("date", "nunique"))
        .reindex(range(24))
        .rename_axis("hour")
        .reset_index()
    )
    return hourly, day_count


def available_history(frame: pd.DataFrame, standard: str) -> pd.DataFrame:
    col = AQI_STANDARDS[standard]["column"]
    return frame.loc[(~frame.is_forecast) & frame[col].notna()].copy()


def anomaly_count(frame: pd.DataFrame, standard: str) -> int | None:
    """Flag hourly AQI points beyond 1.5 IQR; require a full day of valid samples."""
    col = AQI_STANDARDS[standard]["column"]
    values = frame[col].dropna()
    if len(values) < 24:
        return None
    q1, q3 = values.quantile([0.25, 0.75])
    spread = q3 - q1
    if spread == 0:
        return 0
    return int(((values < q1 - 1.5 * spread) | (values > q3 + 1.5 * spread)).sum())


def hottest_pattern_period(frame: pd.DataFrame, standard: str) -> tuple[str, float] | None:
    if frame.empty:
        return None
    col = AQI_STANDARDS[standard]["column"]
    work = frame.dropna(subset=[col]).copy()
    if len(work) < 24:
        return None
    work["hour"] = work.time.dt.hour
    means = work.groupby("hour")[col].mean().reindex(range(24))
    if means.notna().sum() < 3:
        return None
    extended = pd.concat([means, means.iloc[:2]], ignore_index=True)
    windows = extended.rolling(3, min_periods=3).mean().iloc[2:26].reset_index(drop=True)
    start_hour = int(windows.idxmax())
    return f"{start_hour:02d}:00–{(start_hour + 3) % 24:02d}:00", float(windows.iloc[start_hour])

