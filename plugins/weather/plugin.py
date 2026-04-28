"""Weather plugin implementation using a modest Open-Meteo-backed provider."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Handles current weather and short forecast requests for supported locations.

from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any

from model.plugin_runtime import PluginExecutionResult
from weather.provider import (
    DailyForecastPoint,
    HourlyForecastPoint,
    OpenMeteoWeatherProvider,
    ResolvedLocation,
    WeatherProvider,
    WeatherSnapshot,
)

WEATHER_CODE_LABELS = {
    0: "clear",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "foggy",
    48: "depositing rime fog",
    51: "light drizzle",
    53: "moderate drizzle",
    55: "dense drizzle",
    61: "light rain",
    63: "moderate rain",
    65: "heavy rain",
    71: "light snow",
    73: "moderate snow",
    75: "heavy snow",
    80: "light rain showers",
    81: "moderate rain showers",
    82: "violent rain showers",
    95: "thunderstorm",
}


class WeatherPlugin:
    """First real Orac plugin for weather questions."""

    def __init__(self, logger, config_mgr, provider: WeatherProvider | None = None):
        self._logger = logger
        self._config_mgr = config_mgr
        self._provider = provider or OpenMeteoWeatherProvider()

    def can_handle(self, prompt: str) -> bool:
        """Returns whether the prompt looks like a weather question."""
        text = (prompt or "").strip().lower()
        if not text:
            return False
        keywords = (
            "weather",
            "temperature",
            "rain",
            "wind",
            "forecast",
            "coat",
            "umbrella",
            "outside",
        )
        return any(keyword in text for keyword in keywords)

    def execute(self, prompt: str, meta: dict[str, Any] | None = None) -> PluginExecutionResult | None:
        """Executes a weather query and returns a plugin result if handled."""
        if not self.can_handle(prompt):
            return None

        meta = meta or {}
        location_name = self._resolve_location_name(prompt, meta)
        if location_name is None:
            return PluginExecutionResult(
                plugin_id="weather",
                content=(
                    "I can answer weather questions, but I need a location. "
                    "Ask for a place like 'What's the weather in London?' "
                    "or configure a default weather location."
                ),
            )

        try:
            location = self._provider.resolve_location(location_name)
        except Exception as exc:
            self._logger.log_error(f"Weather plugin location lookup failed for '{location_name}': {exc}")
            return PluginExecutionResult(
                plugin_id="weather",
                content="I couldn't resolve that location right now. Please try again shortly.",
            )

        if location is None:
            return PluginExecutionResult(
                plugin_id="weather",
                content=f"I couldn't find a supported location for '{location_name}'.",
            )

        try:
            snapshot = self._provider.get_weather(location)
        except Exception as exc:
            self._logger.log_error(f"Weather plugin forecast lookup failed for '{location.name}': {exc}")
            return PluginExecutionResult(
                plugin_id="weather",
                content="I couldn't retrieve weather data right now. Please try again shortly.",
            )

        response = self._build_response(prompt, snapshot)
        self._logger.log_info(f"Weather plugin handled weather request for {location.name}.")
        return PluginExecutionResult(plugin_id="weather", content=response)

    def _resolve_location_name(self, prompt: str, meta: dict[str, Any]) -> str | None:
        explicit_location = self._extract_explicit_location(prompt)
        if explicit_location:
            return explicit_location

        text = prompt.lower()
        if any(marker in text for marker in ("where i am", "outside", "here", "my area")):
            return (
                meta.get("weather_location")
                or self._config_mgr.config_value("weather", "default_location", default="").strip()
                or None
            )

        return (
            meta.get("weather_location")
            or self._config_mgr.config_value("weather", "default_location", default="").strip()
            or None
        )

    @staticmethod
    def _extract_explicit_location(prompt: str) -> str | None:
        patterns = [
            r"\bweather in ([A-Za-z][A-Za-z .'\-]+)",
            r"\btemperature in ([A-Za-z][A-Za-z .'\-]+)",
            r"\bforecast for ([A-Za-z][A-Za-z .'\-]+)",
            r"\bin ([A-Za-z][A-Za-z .'\-]+)\??$",
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                location = match.group(1).strip(" ?.!,")
                if location:
                    return location
        return None

    def _build_response(self, prompt: str, snapshot: WeatherSnapshot) -> str:
        lowered = prompt.lower()
        if "coat" in lowered or "jacket" in lowered:
            return self._build_coat_response(snapshot, lowered)
        if "rain" in lowered or "umbrella" in lowered:
            return self._build_rain_response(snapshot, lowered)
        if "wind" in lowered:
            return self._build_wind_response(snapshot, lowered)
        if "temperature" in lowered:
            return self._build_temperature_response(snapshot)
        return self._build_general_response(snapshot, lowered)

    def _build_general_response(self, snapshot: WeatherSnapshot, prompt: str) -> str:
        current = snapshot.current
        location_label = self._format_location(snapshot.location)
        outlook = self._select_relevant_hour(snapshot, prompt) or snapshot.hourly[0]
        return (
            f"In {location_label}, it's currently {round(current.temperature_c)}°C and "
            f"{self._describe_code(current.weather_code)}. "
            f"Around {outlook.time.strftime('%H:%M')}, expect about {round(outlook.temperature_c)}°C with "
            f"{self._describe_code(outlook.weather_code)}."
        )

    def _build_temperature_response(self, snapshot: WeatherSnapshot) -> str:
        current = snapshot.current
        location_label = self._format_location(snapshot.location)
        return (
            f"In {location_label}, it's currently {round(current.temperature_c)}°C "
            f"and feels like {round(current.apparent_temperature_c)}°C."
        )

    def _build_rain_response(self, snapshot: WeatherSnapshot, prompt: str) -> str:
        daily = self._select_relevant_day(snapshot, prompt) or snapshot.daily[0]
        hourly = self._select_relevant_hour(snapshot, prompt)
        location_label = self._format_location(snapshot.location)
        if hourly is not None:
            probability = self._format_probability(hourly.precipitation_probability)
            return (
                f"For {location_label} around {hourly.time.strftime('%H:%M')}, "
                f"the outlook is {self._describe_code(hourly.weather_code)} with "
                f"{probability} chance of precipitation."
            )

        probability = self._format_probability(daily.precipitation_probability_max)
        return (
            f"For {location_label} on {daily.date.strftime('%A')}, "
            f"the outlook is {self._describe_code(daily.weather_code)} with "
            f"{probability} chance of precipitation and about {daily.precipitation_sum_mm:.1f} mm expected."
        )

    def _build_wind_response(self, snapshot: WeatherSnapshot, prompt: str) -> str:
        hourly = self._select_relevant_hour(snapshot, prompt)
        location_label = self._format_location(snapshot.location)
        if hourly is not None:
            return (
                f"In {location_label} around {hourly.time.strftime('%H:%M')}, "
                f"winds look to be about {round(hourly.wind_speed_kph)} km/h with "
                f"{self._describe_code(hourly.weather_code)}."
            )

        daily = self._select_relevant_day(snapshot, prompt) or snapshot.daily[0]
        return (
            f"For {location_label} on {daily.date.strftime('%A')}, "
            f"the maximum wind speed looks to be about {round(daily.wind_speed_max_kph)} km/h."
        )

    def _build_coat_response(self, snapshot: WeatherSnapshot, prompt: str) -> str:
        hourly = self._select_relevant_hour(snapshot, prompt)
        if hourly is None:
            hourly = snapshot.hourly[0]
        location_label = self._format_location(snapshot.location)
        cool = hourly.apparent_temperature_c < 12.0
        wet = (hourly.precipitation_probability or 0.0) >= 40.0
        advice_parts = []
        if cool:
            advice_parts.append("I'd take a coat")
        else:
            advice_parts.append("You probably won't need a heavy coat")
        if wet:
            advice_parts.append("and an umbrella would be sensible")

        return (
            f"For {location_label} around {hourly.time.strftime('%H:%M')}, "
            f"it should feel like {round(hourly.apparent_temperature_c)}°C with "
            f"{self._describe_code(hourly.weather_code)}. "
            + " ".join(advice_parts)
            + "."
        )

    @staticmethod
    def _select_relevant_hour(snapshot: WeatherSnapshot, prompt: str) -> HourlyForecastPoint | None:
        text = prompt.lower()
        current_time = snapshot.current.time
        if "tomorrow morning" in text:
            return WeatherPlugin._find_hour(snapshot.hourly, current_time.date() + timedelta(days=1), 9)
        if "this evening" in text or "tonight" in text:
            return WeatherPlugin._find_same_day_hour(snapshot.hourly, current_time.date(), 18)
        if "tomorrow" in text:
            return WeatherPlugin._find_hour(snapshot.hourly, current_time.date() + timedelta(days=1), 12)
        if "today" in text:
            return WeatherPlugin._find_same_day_hour(snapshot.hourly, current_time.date(), 12)
        return None

    @staticmethod
    def _select_relevant_day(snapshot: WeatherSnapshot, prompt: str) -> DailyForecastPoint | None:
        text = prompt.lower()
        current_date = snapshot.current.time.date()
        if "tomorrow" in text:
            for point in snapshot.daily:
                if point.date.date() > current_date:
                    return point
        return snapshot.daily[0] if snapshot.daily else None

    @staticmethod
    def _find_same_day_hour(
        hours: tuple[HourlyForecastPoint, ...],
        day,
        target_hour: int,
    ) -> HourlyForecastPoint | None:
        matching = [point for point in hours if point.time.date() == day]
        if not matching:
            return None
        return min(matching, key=lambda point: abs(point.time.hour - target_hour))

    @staticmethod
    def _find_hour(
        hours: tuple[HourlyForecastPoint, ...],
        target_date,
        target_hour: int,
    ) -> HourlyForecastPoint | None:
        matching = [point for point in hours if point.time.date() == target_date]
        if not matching:
            return None
        return min(matching, key=lambda point: abs(point.time.hour - target_hour))

    @staticmethod
    def _describe_code(code: int) -> str:
        return WEATHER_CODE_LABELS.get(code, "unsettled conditions")

    @staticmethod
    def _format_probability(value: float | None) -> str:
        if value is None:
            return "an unknown"
        return f"about {round(value)}%"

    @staticmethod
    def _format_location(location: ResolvedLocation) -> str:
        parts = [location.name]
        if location.admin1 and location.admin1.lower() != location.name.lower():
            parts.append(location.admin1)
        if location.country:
            parts.append(location.country)
        return ", ".join(parts[:3])
