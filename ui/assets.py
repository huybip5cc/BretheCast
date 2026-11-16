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


def daypart_illustration(period: str) -> str:
    """Return a small, self-contained SVG landscape for one part of the day."""
    scenes = {
        "morning": {
            "sky": ("#f4b995", "#e8e9dc"),
            "sun": '<circle cx="70" cy="94" r="25" fill="#ffd17f"/>',
            "cloud": '<path d="M180 53c2-10 17-14 25-6 8-15 31-10 32 7 13-2 18 16 5 19h-55c-12-1-16-13-7-20Z" fill="#fff" opacity=".62"/>',
            "far": "#91aa8d",
            "near": "#648875",
            "city": "#657d78",
            "stars": "",
        },
        "noon": {
            "sky": ("#73c4e9", "#e2f4e9"),
            "sun": '<circle cx="246" cy="34" r="22" fill="#ffe17b"/>',
            "cloud": '<path d="M62 49c2-11 18-15 27-7 9-16 33-11 34 7 13-2 19 17 5 20H73c-13-1-17-13-11-20Z" fill="#fff" opacity=".72"/>',
            "far": "#9ccf9f",
            "near": "#67a995",
            "city": "#6d9d90",
            "stars": "",
        },
        "afternoon": {
            "sky": ("#67a9d6", "#f6d3a2"),
            "sun": '<circle cx="229" cy="62" r="24" fill="#ffd17d"/>',
            "cloud": '<path d="M40 48c2-10 17-14 25-6 8-15 31-10 32 7 13-2 18 16 5 19H53c-12-1-16-13-13-20Z" fill="#fff" opacity=".52"/>',
            "far": "#9bb38b",
            "near": "#6b9278",
            "city": "#71877d",
            "stars": "",
        },
        "evening": {
            "sky": ("#e88168", "#f6c486"),
            "sun": '<circle cx="257" cy="96" r="27" fill="#ffe09a"/>',
            "cloud": '<path d="M66 43c2-10 17-14 25-6 8-15 31-10 32 7 13-2 18 16 5 19H79c-12-1-16-13-13-20Z" fill="#fff" opacity=".42"/>',
            "far": "#806d72",
            "near": "#4d596c",
            "city": "#465369",
            "stars": "",
        },
        "night": {
            "sky": ("#17234b", "#465783"),
            "sun": '<path d="M237 20a21 21 0 1 0 22 34 17 17 0 0 1-22-34Z" fill="#f5e8b5"/>',
            "cloud": '<path d="M51 62c2-9 16-13 23-5 8-13 27-9 29 6 12-2 16 14 4 17H63c-11-1-15-11-12-18Z" fill="#bcc9e6" opacity=".25"/>',
            "far": "#394765",
            "near": "#202d4b",
            "city": "#192440",
            "stars": '<g fill="#fff1bd"><circle cx="48" cy="25" r="1.7"/><circle cx="103" cy="20" r="1.2"/><circle cx="147" cy="41" r="1.4"/><circle cx="190" cy="17" r="1.6"/><circle cx="290" cy="60" r="1.2"/></g>',
        },
    }
    scene = scenes.get(period, scenes["morning"])
    key = period if period in scenes else "morning"
    sky_top, sky_bottom = scene["sky"]
    return (
        f'<svg class="daypart-illustration" viewBox="0 0 320 140" '
        f'preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">'
        f'<defs><linearGradient id="daypart-sky-{key}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop stop-color="{sky_top}"/><stop offset="1" stop-color="{sky_bottom}"/>'
        f'</linearGradient></defs><path fill="url(#daypart-sky-{key})" d="M0 0h320v140H0z"/>'
        f'{scene["stars"]}{scene["sun"]}{scene["cloud"]}'
        f'<path d="M0 107Q62 77 132 100T260 93Q294 88 320 97V140H0Z" fill="{scene["far"]}"/>'
        f'<path d="M0 111V95h20V79h18v32h12V88h24v23h15V72h20v39h15V84h27v27h17V67h21v44h19V82h25v29h17V75h20v36h20v29H0Z" fill="{scene["city"]}"/>'
        f'<path d="M0 117Q72 96 144 113T320 107V140H0Z" fill="{scene["near"]}"/>'
        f'</svg>'
    )


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
