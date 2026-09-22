import json

from helpers import FIXTURES
from mailer import banners
import weather

REAL_DAY = json.loads((FIXTURES / "open_meteo_2026-09-22.json").read_text())


def day(codes, rain=0, temps=60.0, wind=3.0, gust=8.0):
    """A fake 24-hour forecast with the same code every hour unless a list is given."""
    codes = codes if isinstance(codes, list) else [codes] * 24
    return {"hourly": {
        "time": [f"2026-09-22T{h:02d}:00" for h in range(24)],
        "temperature_2m": [temps] * 24,
        "precipitation_probability": [rain] * 24,
        "weather_code": codes,
        "wind_speed_10m": [wind] * 24,
        "wind_gusts_10m": [gust] * 24,
    }}


def test_real_forecast_reads_as_three_parts():
    f = weather.parse(REAL_DAY)
    assert f.line == "Morning 61°, cloudy · Afternoon 69°, partly cloudy · Tonight 63°, mostly clear"
    # A mix of cloud and sun with nothing else going on counts as a normal day.
    assert f.condition == weather.NORMAL


def test_overcast_all_day_is_cloudy():
    assert weather.parse(day(3)).condition == weather.CLOUDY


def test_windy_day():
    f = weather.parse(day(2, gust=38))
    assert f.condition == weather.WINDY
    assert "partly cloudy and windy" in f.line


def test_rain_beats_wind():
    assert weather.parse(day(63, rain=80, gust=40)).condition == weather.RAINY


def test_older_responses_without_wind_still_parse():
    data = day(0)
    del data["hourly"]["wind_speed_10m"], data["hourly"]["wind_gusts_10m"]
    assert weather.parse(data).condition == weather.SUNNY


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
    from datetime import date
    for name in ("header.png", "Rainy Day.png", "sunny.png", "footer.png"):
        (tmp_path / name).write_bytes(b"\x89PNG")
    headers = {"rainy": ("Rainy Day.png",), "sunny": ("sunny.png", "header.png"), "snowy": ("missing.png",)}
    tuesday, wednesday = date(2026, 9, 22), date(2026, 9, 23)

    assert banners.header_for("rainy", tuesday, headers, tmp_path) == "Rainy Day.png"
    # Two choices take turns, so consecutive sunny days get different headers.
    assert {banners.header_for("sunny", d, headers, tmp_path) for d in (tuesday, wednesday)} == {"sunny.png", "header.png"}
    # Missing files, unknown weather, and no forecast all fall back to the default.
    assert banners.header_for("snowy", tuesday, headers, tmp_path) == "header.png"
    assert banners.header_for("windy", tuesday, headers, tmp_path) == "header.png"
    assert banners.header_for(None, tuesday, headers, tmp_path) == "header.png"

    picked = banners.available("Rainy Day.png", tmp_path)
    assert [b.path.name for b in picked] == ["Rainy Day.png", "footer.png"]


def test_header_names_ignore_case(tmp_path):
    from datetime import date
    (tmp_path / "header.png").write_bytes(b"\x89PNG")
    (tmp_path / "Email.Header.Rainy.PNG").write_bytes(b"\x89PNG")
    picked = banners.header_for("rainy", date(2026, 9, 22), {"rainy": ("Email.Header.Rainy.png",)}, tmp_path)
    assert picked == "Email.Header.Rainy.PNG"
    assert banners.available(picked, tmp_path)[0].path.name == "Email.Header.Rainy.PNG"


def test_every_kind_of_weather_has_a_header(prefs):
    assert set(prefs.headers) == set(weather.CONDITIONS)
