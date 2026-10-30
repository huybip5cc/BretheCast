"""Shared dashboard assets and formatting helpers."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

import pandas as pd

def weather_text(code: int | float | None) -> tuple[str, str]:
    if code is None or pd.isna(code):
        return "—", ""
    code = int(code)
    if code == 0:
        return "Trời nắng", ""
    if code in (1, 2, 3):
        return ("Ít mây" if code < 3 else "Nhiều mây"), ""
    if code in (45, 48):
        return "Sương mù", ""
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "Có mưa", ""
    if 71 <= code <= 77 or 85 <= code <= 86:
        return "Nhiều mây", ""
    if code >= 95:
        return "Dông", ""
    return "Nhiều mây", ""


def weather_icon_filename(code: int | float | None) -> str:
    if code is None or pd.isna(code):
        return "sunrise.png"
    code = int(code)
    if code == 0:
        return "strong-sun.png"
    if code in (1, 2):
        return "sunrise.png"
    if code in (3, 45, 48) or 71 <= code <= 77 or 85 <= code <= 86:
        return "clouds.png"
    if 51 <= code <= 57 or 80 <= code <= 81:
        return "rainy-day-sun.png"
    if 61 <= code <= 67 or code == 82:
        return "rainy-day.png"
    if code >= 95:
        return "thunderstorm.png"
    return "sunrise.png"


@lru_cache(maxsize=8)
def weather_icon_data(filename: str) -> str:
    image_path = Path(__file__).resolve().parent.parent / "assets" / "weather" / filename
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@lru_cache(maxsize=4)
def aqi_icon_data(filename: str) -> str:
    image_path = Path(__file__).resolve().parent.parent / "assets" / "aqi" / filename
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def aqi_forecast_icon_filename(label: str) -> str:
    if label == "Tốt":
        return "awareness-green.png"
    if label in ("Khá", "Trung bình"):
        return "awareness-yellow.png"
    return "awareness-dark.png"


def weather_icon(code: int | float | None, size: int, label: str | None = None) -> str:
    alt = label or weather_text(code)[0]
    src = weather_icon_data(weather_icon_filename(code))
    return f'<img class="weather-icon" src="{src}" width="{size}" height="{size}" alt="{alt}">'


def city_svg(city: str) -> str:
    if city == "Hà Nội":
        shapes = '<path d="M0 82h400v56H0z" fill="#596b70"/><path d="M32 54h45v84H32zm53-17h57v101H85zm65 31h46v70h-46zm54-27h74v97h-74zm83 21h53v76h-53zm60-15h43v91h-43z" fill="#40545b"/><path d="M51 63h4v5h-4zm14 0h4v5h-4zm32-10h5v6h-5zm17 0h5v6h-5zm84 28h5v6h-5zm21 0h5v6h-5zm65-8h5v6h-5z" fill="#f1c985"/><path d="M0 137h400" stroke="#e7d0a9" stroke-width="3"/>'
    else:
        shapes = '<path d="M0 82h400v56H0z" fill="#567177"/><path d="M22 70h48v68H22zm56-36h59v104H78zm68 20h48v84h-48zm58-41h66v125h-66zm75 45h48v80h-48zm55-28h42v108h-42z" fill="#41565d"/><path d="M93 48h5v6h-5zm17 0h5v6h-5zm49 18h5v6h-5zm61-37h5v6h-5zm18 0h5v6h-5zm52 40h5v6h-5zm48-28h5v6h-5z" fill="#efcf95"/><path d="M0 137h400" stroke="#e7d0a9" stroke-width="3"/>'
    return f'<svg viewBox="0 0 400 150" preserveAspectRatio="xMidYMid slice"><defs><linearGradient id="citysky" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#b8c8c8"/><stop offset="1" stop-color="#e2d0b5"/></linearGradient></defs><path fill="url(#citysky)" d="M0 0h400v150H0z"/>{shapes}</svg>'


def fmt(value, digits=0):
    return "—" if value is None or pd.isna(value) else f"{value:.{digits}f}"


def direction(degrees):
    if degrees is None or pd.isna(degrees):
        return "—"
    points = ("B", "BĐB", "ĐB", "ĐĐB", "Đ", "ĐĐN", "ĐN", "NĐN", "N", "NTN", "TN", "TBTN", "T", "TB", "TTB", "BTTB")
    return points[int((float(degrees) + 11.25) // 22.5) % 16]
