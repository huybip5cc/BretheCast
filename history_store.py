"""Persist actual returned hourly CAMS archive values for local continuity."""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent / ".aqi_data" / "history.sqlite3"


def store_archive(city: str, frame: pd.DataFrame) -> None:
    """Keep the first value returned for each past timestamp; never store forecasts."""
    if frame.empty:
        return
    past = frame.loc[~frame["is_forecast"]].copy()
    if past.empty:
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    columns = ["time", "us_aqi", "european_aqi", "pm2_5"]
    rows = []
    for _, row in past[columns].iterrows():
        rows.append((city, row["time"].isoformat(), *(None if pd.isna(row[c]) else float(row[c]) for c in columns[1:])))
    with sqlite3.connect(DB_PATH, timeout=4) as connection:
        connection.execute("""CREATE TABLE IF NOT EXISTS hourly_archive (
            city TEXT NOT NULL,
            time TEXT NOT NULL,
            us_aqi REAL,
            european_aqi REAL,
            pm2_5 REAL,
            PRIMARY KEY (city, time)
        )""")
        connection.executemany(
            "INSERT OR IGNORE INTO hourly_archive(city,time,us_aqi,european_aqi,pm2_5) VALUES(?,?,?,?,?)",
            rows,
        )


def load_archive(city: str) -> pd.DataFrame:
    """Read locally saved model-history points for a clearly marked offline view."""
    if not DB_PATH.exists():
        return pd.DataFrame()
    try:
        with sqlite3.connect(DB_PATH, timeout=4) as connection:
            frame = pd.read_sql_query(
                "SELECT time,us_aqi,european_aqi,pm2_5 FROM hourly_archive WHERE city=? ORDER BY time",
                connection,
                params=(city,),
            )
    except sqlite3.Error:
        return pd.DataFrame()
    if frame.empty:
        return frame
    frame["time"] = pd.to_datetime(frame["time"], errors="coerce")
    frame = frame.dropna(subset=["time"])
    cutoff = pd.Timestamp.now(tz="Asia/Ho_Chi_Minh").tz_localize(None) - timedelta(days=90)
    frame = frame.loc[frame["time"] >= cutoff].copy()
    frame["date"] = frame["time"].dt.date
    frame["is_forecast"] = False
    for column in ("us_aqi", "european_aqi", "pm2_5"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame

