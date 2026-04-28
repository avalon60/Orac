"""Tests for the Orac weather plugin implementation."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Verifies the weather plugin execution seam and provider behaviour without live network calls.

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

from weather.plugin import WeatherPlugin
from weather.provider import (
    OpenMeteoWeatherProvider,
    ResolvedLocation,
    StubWeatherProvider,
    WeatherSnapshot,
    CurrentConditions,
    HourlyForecastPoint,
    DailyForecastPoint,
)


class _FakeLogger:
    def __init__(self):
        self.messages: list[tuple[str, str]] = []

    def log_info(self, message: str) -> None:
        self.messages.append(("info", message))

    def log_error(self, message: str) -> None:
        self.messages.append(("error", message))


class _FakeConfigManager:
    def __init__(self, default_location: str = ""):
        self._default_location = default_location

    def config_value(self, section: str, key: str, default: str = "") -> str:
        if section == "weather" and key == "default_location":
            return self._default_location
        return default


def _build_snapshot() -> WeatherSnapshot:
    location = ResolvedLocation(
        name="London",
        latitude=51.5072,
        longitude=-0.1276,
        timezone="Europe/London",
        country="United Kingdom",
        admin1="England",
    )
    current = CurrentConditions(
        time=datetime.fromisoformat("2026-04-23T10:00:00"),
        temperature_c=14.0,
        apparent_temperature_c=12.0,
        wind_speed_kph=18.0,
        precipitation_mm=0.0,
        weather_code=2,
    )
    hourly = (
        HourlyForecastPoint(
            time=datetime.fromisoformat("2026-04-23T18:00:00"),
            temperature_c=10.0,
            apparent_temperature_c=8.0,
            precipitation_probability=55.0,
            precipitation_mm=1.2,
            wind_speed_kph=20.0,
            weather_code=61,
        ),
        HourlyForecastPoint(
            time=datetime.fromisoformat("2026-04-24T09:00:00"),
            temperature_c=9.0,
            apparent_temperature_c=7.0,
            precipitation_probability=15.0,
            precipitation_mm=0.0,
            wind_speed_kph=28.0,
            weather_code=3,
        ),
    )
    daily = (
        DailyForecastPoint(
            date=datetime.fromisoformat("2026-04-23"),
            temperature_max_c=15.0,
            temperature_min_c=8.0,
            precipitation_probability_max=60.0,
            precipitation_sum_mm=2.1,
            wind_speed_max_kph=23.0,
            weather_code=61,
        ),
        DailyForecastPoint(
            date=datetime.fromisoformat("2026-04-24"),
            temperature_max_c=13.0,
            temperature_min_c=7.0,
            precipitation_probability_max=20.0,
            precipitation_sum_mm=0.1,
            wind_speed_max_kph=29.0,
            weather_code=3,
        ),
    )
    return WeatherSnapshot(location=location, current=current, hourly=hourly, daily=daily)


class WeatherPluginTests(unittest.TestCase):
    """Tests the first real Orac plugin implementation."""

    def test_weather_plugin_handles_temperature_question(self) -> None:
        snapshot = _build_snapshot()
        provider = StubWeatherProvider(location=snapshot.location, snapshot=snapshot)
        plugin = WeatherPlugin(
            logger=_FakeLogger(),
            config_mgr=_FakeConfigManager(),
            provider=provider,
        )

        result = plugin.execute("What's the weather in London?")

        self.assertIsNotNone(result)
        self.assertEqual(result.plugin_id, "weather")
        self.assertIn("London", result.content)

    def test_weather_plugin_asks_for_location_when_none_available(self) -> None:
        snapshot = _build_snapshot()
        provider = StubWeatherProvider(location=snapshot.location, snapshot=snapshot)
        plugin = WeatherPlugin(
            logger=_FakeLogger(),
            config_mgr=_FakeConfigManager(default_location=""),
            provider=provider,
        )

        result = plugin.execute("What is the temperature?")

        self.assertIsNotNone(result)
        self.assertIn("need a location", result.content)

    def test_weather_plugin_uses_default_location_for_here_question(self) -> None:
        snapshot = _build_snapshot()
        provider = StubWeatherProvider(location=snapshot.location, snapshot=snapshot)
        plugin = WeatherPlugin(
            logger=_FakeLogger(),
            config_mgr=_FakeConfigManager(default_location="London"),
            provider=provider,
        )

        result = plugin.execute("Will it rain today where I am?")

        self.assertIsNotNone(result)
        self.assertIn("London", result.content)

    def test_weather_plugin_returns_graceful_failure_when_provider_errors(self) -> None:
        provider = Mock()
        provider.resolve_location.return_value = ResolvedLocation(
            name="London",
            latitude=51.0,
            longitude=-0.1,
            timezone="Europe/London",
            country="United Kingdom",
            admin1="England",
        )
        provider.get_weather.side_effect = RuntimeError("network down")
        plugin = WeatherPlugin(
            logger=_FakeLogger(),
            config_mgr=_FakeConfigManager(),
            provider=provider,
        )

        result = plugin.execute("What's the weather in London?")

        self.assertIsNotNone(result)
        self.assertIn("couldn't retrieve weather data", result.content)


class OpenMeteoProviderTests(unittest.TestCase):
    """Tests the Open-Meteo provider using mocked HTTP responses."""

    def test_resolve_location_parses_response(self) -> None:
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "results": [
                {
                    "name": "London",
                    "latitude": 51.5072,
                    "longitude": -0.1276,
                    "timezone": "Europe/London",
                    "country": "United Kingdom",
                    "admin1": "England",
                }
            ]
        }
        response.raise_for_status.return_value = None
        session.get.return_value = response
        provider = OpenMeteoWeatherProvider(session=session)

        location = provider.resolve_location("London")

        self.assertIsNotNone(location)
        self.assertEqual(location.name, "London")
        self.assertEqual(location.timezone, "Europe/London")

    def test_get_weather_parses_forecast_payload(self) -> None:
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "current": {
                "time": "2026-04-23T10:00",
                "temperature_2m": 14.0,
                "apparent_temperature": 12.0,
                "precipitation": 0.0,
                "weather_code": 2,
                "wind_speed_10m": 18.0,
            },
            "hourly": {
                "time": ["2026-04-23T18:00", "2026-04-24T09:00"],
                "temperature_2m": [10.0, 9.0],
                "apparent_temperature": [8.0, 7.0],
                "precipitation_probability": [55.0, 15.0],
                "precipitation": [1.2, 0.0],
                "weather_code": [61, 3],
                "wind_speed_10m": [20.0, 28.0],
            },
            "daily": {
                "time": ["2026-04-23", "2026-04-24"],
                "temperature_2m_max": [15.0, 13.0],
                "temperature_2m_min": [8.0, 7.0],
                "precipitation_probability_max": [60.0, 20.0],
                "precipitation_sum": [2.1, 0.1],
                "wind_speed_10m_max": [23.0, 29.0],
                "weather_code": [61, 3],
            },
        }
        response.raise_for_status.return_value = None
        session.get.return_value = response
        provider = OpenMeteoWeatherProvider(session=session)
        location = ResolvedLocation(
            name="London",
            latitude=51.5072,
            longitude=-0.1276,
            timezone="Europe/London",
            country="United Kingdom",
            admin1="England",
        )

        snapshot = provider.get_weather(location)

        self.assertEqual(snapshot.location.name, "London")
        self.assertEqual(len(snapshot.hourly), 2)
        self.assertEqual(len(snapshot.daily), 2)
        self.assertEqual(snapshot.current.weather_code, 2)


if __name__ == "__main__":
    unittest.main()
