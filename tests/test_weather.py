import json

from helpers import FIXTURES
from mailer import banners
import weather

REAL_DAY = json.loads((FIXTURES / "open_meteo_2026-09-22.json").read_text())


def day(codes, rain=0, temps=60.0):
    """A fake 24-hour forecast with the same code every hour unless a list is given."""
    codes = codes if isinstance(codes, list) else [codes] * 24
    return {"hourly": {
        "time": [f"2026-09-22T{h:02d}:00" for h in range(24)],
        "temperature_2m": [temps] * 24,
        "precipitation_probability": [rain] * 24,
        "weather_code": codes,
    }}


def test_real_forecast_reads_as_three_parts():
    f = weather.parse(REAL_DAY)
    assert f.line == "Morning 61°, cloudy · Afternoon 69°, partly cloudy · Tonight 63°, mostly clear"
    assert f.condition == weather.CLOUDY


def test_clear_day_is_sunny():
    f = weather.parse(day(0))
    assert f.condition == weather.SUNNY
    assert "Morning 60°, sunny" in f.line
    assert "Tonight 60°, clear" in f.line


def test_rain_shows_with_its_chance():
    f = weather.parse(day(63, rain=80))
    assert f.condition == weather.RAINY
    assert "Afternoon 60°, rain (80%)" in f.line


def test_rain_chance_mentioned_even_when_sky_is_just_cloudy():
    f = weather.parse(day(3, rain=40))
    assert "cloudy, 40% chance of rain" in f.line


def test_low_rain_chance_is_left_out():
    assert "chance" not in weather.parse(day(3, rain=10)).line


def test_single_hour_of_drizzle_doesnt_make_the_day_rainy():
    codes = [2] * 24
    codes[9] = 51
    f = weather.parse(day(codes))
    assert f.condition != weather.RAINY
    assert "drizzle" not in f.line


def test_thunder_and_snow():
    assert weather.parse(day(95)).condition == weather.STORMY
    assert weather.parse(day(73)).condition == weather.SNOWY


def test_empty_response_gives_no_forecast():
    assert weather.parse({}) is None


def test_fetch_failure_returns_none(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("offline")
    monkeypatch.setattr(weather.net, "get_json", boom)
    from datetime import date
    assert weather.fetch(45.5, -122.6, date(2026, 9, 22), "America/Los_Angeles") is None


def test_header_follows_the_weather(tmp_path):
    for name in ("header.png", "header-rainy.png", "footer.png"):
        (tmp_path / name).write_bytes(b"\x89PNG")
    rainy = banners.available("rainy", assets=tmp_path)
    assert rainy[0].path.name == "header-rainy.png"
    # No header-sunny.png, so a sunny day falls back to the default.
    assert banners.available("sunny", assets=tmp_path)[0].path.name == "header.png"
    assert banners.available(None, assets=tmp_path)[0].path.name == "header.png"
