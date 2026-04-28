"""Weather provider abstraction and Open-Meteo implementation for the weather plugin."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Encapsulates weather and geocoding access behind a narrow provider interface.

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests


@dataclass(frozen=True)
class ResolvedLocation:
    """Represents a resolved place suitable for weather forecast lookup."""

    name: str
    latitude: float
    longitude: float
    timezone: str
    country: str | None = None
    admin1: str | None = None


@dataclass(frozen=True)
class CurrentConditions:
    """Represents the current weather conditions for a location."""

    time: datetime
    temperature_c: float
    apparent_temperature_c: float
    wind_speed_kph: float
    precipitation_mm: float
    weather_code: int


@dataclass(frozen=True)
class HourlyForecastPoint:
    """Represents one hourly forecast point."""

    time: datetime
    temperature_c: float
    apparent_temperature_c: float
    precipitation_probability: float | None
    precipitation_mm: float
    wind_speed_kph: float
    weather_code: int


@dataclass(frozen=True)
class DailyForecastPoint:
    """Represents one daily forecast summary point."""

    date: datetime
    temperature_max_c: float
    temperature_min_c: float
    precipitation_probability_max: float | None
    precipitation_sum_mm: float
    wind_speed_max_kph: float
    weather_code: int


@dataclass(frozen=True)
class WeatherSnapshot:
    """Aggregates current, hourly, and daily weather data for a location."""

    location: ResolvedLocation
    current: CurrentConditions
    hourly: tuple[HourlyForecastPoint, ...]
    daily: tuple[DailyForecastPoint, ...]


class WeatherProvider(ABC):
    """Abstraction for resolving locations and fetching weather data."""

    @abstractmethod
    def resolve_location(self, location_name: str) -> ResolvedLocation | None:
        """Resolves a human-readable location name to coordinates."""

    @abstractmethod
    def get_weather(self, location: ResolvedLocation) -> WeatherSnapshot:
        """Returns weather data for a resolved location."""


class OpenMeteoWeatherProvider(WeatherProvider):
    """Open-Meteo-backed provider for current conditions and short forecasts."""

    GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, session: requests.Session | None = None, timeout: tuple[int, int] = (5, 15)):
        self._session = session or requests.Session()
        self._timeout = timeout

    def resolve_location(self, location_name: str) -> ResolvedLocation | None:
        response = self._session.get(
            self.GEOCODING_URL,
            params={
                "name": location_name,
                "count": 1,
                "language": "en",
                "format": "json",
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        results = payload.get("results") or []
        if not results:
            return None

        record = results[0]
        return ResolvedLocation(
            name=record["name"],
            latitude=float(record["latitude"]),
            longitude=float(record["longitude"]),
            timezone=record.get("timezone", "UTC"),
            country=record.get("country"),
            admin1=record.get("admin1"),
        )

    def get_weather(self, location: ResolvedLocation) -> WeatherSnapshot:
        response = self._session.get(
            self.FORECAST_URL,
            params={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "timezone": location.timezone,
                "forecast_days": 3,
                "current": [
                    "temperature_2m",
                    "apparent_temperature",
                    "precipitation",
                    "weather_code",
                    "wind_speed_10m",
                ],
                "hourly": [
                    "temperature_2m",
                    "apparent_temperature",
                    "precipitation_probability",
                    "precipitation",
                    "weather_code",
                    "wind_speed_10m",
                ],
                "daily": [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_probability_max",
                    "precipitation_sum",
                    "wind_speed_10m_max",
                ],
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()

        current = self._parse_current(payload["current"])
        hourly = self._parse_hourly(payload["hourly"])
        daily = self._parse_daily(payload["daily"])
        return WeatherSnapshot(location=location, current=current, hourly=hourly, daily=daily)

    @staticmethod
    def _parse_current(payload: dict[str, Any]) -> CurrentConditions:
        return CurrentConditions(
            time=datetime.fromisoformat(payload["time"]),
            temperature_c=float(payload["temperature_2m"]),
            apparent_temperature_c=float(payload["apparent_temperature"]),
            wind_speed_kph=float(payload["wind_speed_10m"]),
            precipitation_mm=float(payload["precipitation"]),
            weather_code=int(payload["weather_code"]),
        )

    @staticmethod
    def _parse_hourly(payload: dict[str, Any]) -> tuple[HourlyForecastPoint, ...]:
        points: list[HourlyForecastPoint] = []
        times = payload.get("time", [])
        for index, raw_time in enumerate(times):
            precip_prob_values = payload.get("precipitation_probability")
            points.append(
                HourlyForecastPoint(
                    time=datetime.fromisoformat(raw_time),
                    temperature_c=float(payload["temperature_2m"][index]),
                    apparent_temperature_c=float(payload["apparent_temperature"][index]),
                    precipitation_probability=(
                        float(precip_prob_values[index]) if precip_prob_values is not None else None
                    ),
                    precipitation_mm=float(payload["precipitation"][index]),
                    wind_speed_kph=float(payload["wind_speed_10m"][index]),
                    weather_code=int(payload["weather_code"][index]),
                )
            )
        return tuple(points)

    @staticmethod
    def _parse_daily(payload: dict[str, Any]) -> tuple[DailyForecastPoint, ...]:
        points: list[DailyForecastPoint] = []
        dates = payload.get("time", [])
        for index, raw_date in enumerate(dates):
            precip_prob_values = payload.get("precipitation_probability_max")
            points.append(
                DailyForecastPoint(
                    date=datetime.fromisoformat(raw_date),
                    temperature_max_c=float(payload["temperature_2m_max"][index]),
                    temperature_min_c=float(payload["temperature_2m_min"][index]),
                    precipitation_probability_max=(
                        float(precip_prob_values[index]) if precip_prob_values is not None else None
                    ),
                    precipitation_sum_mm=float(payload["precipitation_sum"][index]),
                    wind_speed_max_kph=float(payload["wind_speed_10m_max"][index]),
                    weather_code=int(payload["weather_code"][index]),
                )
            )
        return tuple(points)


class StubWeatherProvider(WeatherProvider):
    """Deterministic provider for plugin tests."""

    def __init__(self, location: ResolvedLocation, snapshot: WeatherSnapshot):
        self._location = location
        self._snapshot = snapshot

    def resolve_location(self, location_name: str) -> ResolvedLocation | None:
        if location_name.strip().lower() == self._location.name.lower():
            return self._location
        return None

    def get_weather(self, location: ResolvedLocation) -> WeatherSnapshot:
        return self._snapshot
