"""Today's weather in three parts (morning, afternoon, tonight) for the line
under the date, plus one word for the whole day that picks the header image.

Forecast from Open-Meteo: free, no key, hourly data in local time.
https://open-meteo.com/en/docs
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import date
from statistics import mean
from typing import Optional

import net

URL = "https://api.open-meteo.com/v1/forecast"
RAIN_CHANCE_WORTH_MENTIONING = 30  # percent
WINDY_SUSTAINED_MPH = 18
WINDY_GUST_MPH = 30

# (label, first hour, last hour, which temperature to show)
PERIODS = (
    ("Morning", 7, 11, "average"),
    ("Afternoon", 12, 17, "high"),
    ("Tonight", 18, 22, "average"),
)

# The day's one-word condition, which picks the header (see [headers] in
# preferences.toml). Checked in this order; the first that fits wins.
STORMY, SNOWY, RAINY, WINDY, CLOUDY, SUNNY, NORMAL = (
    "stormy", "snowy", "rainy", "windy", "cloudy", "sunny", "normal")
CONDITIONS = (STORMY, SNOWY, RAINY, WINDY, CLOUDY, SUNNY, NORMAL)

# WMO weather codes, as Open-Meteo reports them.
_THUNDER = set(range(95, 100))
_SNOW = {71, 73, 75, 77, 85, 86}
_RAIN = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}
_FOG = {45, 48}
_WET_WORDS = {
    **{c: "drizzle" for c in (51, 53, 55, 56, 57)},
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
    80: "showers", 81: "showers", 82: "heavy showers",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow", 85: "snow showers", 86: "snow showers",
    **{c: "thunderstorms" for c in _THUNDER},
}

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Hour:
    temp: float
    rain: int
    code: int
    wind: float
    gust: float

    @property
    def windy(self) -> bool:
        return self.wind >= WINDY_SUSTAINED_MPH or self.gust >= WINDY_GUST_MPH


@dataclass(frozen=True)
class Period:
    label: str
    temp: int
    sky: str
    rain_chance: int
    windy: bool = False

    def __str__(self) -> str:
        text = f"{self.label} {self.temp}°, {self.sky}"
        if self.windy:
            text += " and windy"
        wet = any(w in self.sky for w in ("rain", "drizzle", "shower", "snow", "thunder"))
        if self.rain_chance >= RAIN_CHANCE_WORTH_MENTIONING:
            text += f" ({self.rain_chance}%)" if wet else f", {self.rain_chance}% chance of rain"
        return text


@dataclass(frozen=True)
class Forecast:
    periods: tuple[Period, ...]
    condition: str

    @property
    def line(self) -> str:
        return " · ".join(str(p) for p in self.periods)


def fetch(latitude: float, longitude: float, day: date, timezone: str) -> Optional[Forecast]:
    """Today's forecast, or None if the weather service can't be reached.
    The email goes out either way."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,precipitation_probability,weather_code,wind_speed_10m,wind_gusts_10m",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": timezone,
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
    }
    try:
        return parse(net.get_json(URL, params=params))
    except Exception as exc:
        log.warning("Weather: couldn't get a forecast (%s)", exc)
        return None


def parse(data: dict) -> Optional[Forecast]:
    hourly = data.get("hourly") or {}
    times = hourly.get("time", [])

    def column(name: str) -> list:
        values = hourly.get(name) or []
        return list(values) + [None] * (len(times) - len(values))

    hours: dict[int, Hour] = {}
    for t, temp, rain, code, wind, gust in zip(
        times, column("temperature_2m"), column("precipitation_probability"),
        column("weather_code"), column("wind_speed_10m"), column("wind_gusts_10m"),
    ):
        if temp is None or code is None:
            continue
        hours[int(t[11:13])] = Hour(temp, rain or 0, code, wind or 0.0, gust or 0.0)

    periods = []
    for label, first, last, which in PERIODS:
        rows = [hours[h] for h in range(first, last + 1) if h in hours]
        if not rows:
            continue
        temps = [r.temp for r in rows]
        periods.append(Period(
            label=label,
            temp=round(max(temps) if which == "high" else mean(temps)),
            sky=_describe([r.code for r in rows], night=label == "Tonight"),
            rain_chance=max(r.rain for r in rows),
            windy=sum(r.windy for r in rows) >= 2,
        ))
    if not periods:
        return None
    daytime = [hours[h] for h in range(7, 23) if h in hours]
    return Forecast(tuple(periods), _condition(daytime))


def _describe(codes: list[int], night: bool) -> str:
    """Wet weather wins if it shows up for at least two hours (thunder for
    one); otherwise the average cloud cover decides."""
    if any(c in _THUNDER for c in codes):
        return "thunderstorms"
    wet = [c for c in codes if c in _WET_WORDS]
    if len(wet) >= 2:
        return _WET_WORDS[Counter(wet).most_common(1)[0][0]]
    if sum(c in _FOG for c in codes) * 2 >= len(codes):
        return "foggy"
    cover = mean([c for c in codes if c <= 3] or [3])
    if cover < 0.5:
        return "clear" if night else "sunny"
    if cover < 1.5:
        return "mostly clear" if night else "mostly sunny"
    if cover < 2.5:
        return "partly cloudy"
    return "cloudy"


def _condition(rows: list[Hour]) -> str:
    codes = [r.code for r in rows]
    if any(c in _THUNDER for c in codes):
        return STORMY
    if sum(c in _SNOW for c in codes) >= 2:
        return SNOWY
    if sum(c in _RAIN for c in codes) >= 2 or max((r.rain for r in rows), default=0) >= 60:
        return RAINY
    if sum(r.windy for r in rows) >= 2:
        return WINDY
    if sum(c in _FOG for c in codes) * 2 >= len(codes):
        return CLOUDY
    sky = [c for c in codes if c <= 3]
    cover = mean(sky) if sky else 3
    if cover >= 2.3:
        return CLOUDY
    if cover < 1.0:
        return SUNNY
    return NORMAL
