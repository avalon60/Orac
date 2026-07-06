"""Weather plugin implementation using a modest Open-Meteo-backed provider."""
# Author: Clive Bostock
# Date: 2026-04-30
# Description: Handles current weather and short forecast requests for supported locations.

from __future__ import annotations

from datetime import datetime, timedelta
import math
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

    def __init__(
        self,
        logger,
        config_mgr,
        data_access=None,
        provider: WeatherProvider | None = None,
    ):
        self._logger = logger
        self._config_mgr = config_mgr
        self._data_access = data_access
        self._provider = provider or OpenMeteoWeatherProvider()

    def can_handle(self, prompt: str) -> bool:
        """Returns whether the prompt looks like a weather question."""
        text = (prompt or "").strip().lower()
        if not text:
            return False
        generic_temperature_question = re.fullmatch(
            r"(?:what is|what's) (?:the )?temperature\??",
            text,
        )
        if (
            generic_temperature_question is None
            and "temperature" in text
            and "weather" not in text
            and "outside" not in text
            and not re.search(r"\btemperature in\b", text)
            and re.search(r"\b(?:what is|what's) (?:the )?.+ temperature\b", text)
        ):
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
        resolved_location = self._resolve_location(prompt, meta)
        if resolved_location is None:
            return PluginExecutionResult(
                plugin_id="weather",
                content=(
                    "I can answer weather questions, but I need a location. "
                    "Ask for a place like 'What's the weather in London?' "
                    "or configure a default user location."
                ),
            )

        if isinstance(resolved_location, ResolvedLocation):
            location = resolved_location
        else:
            location_name = resolved_location
            location = self._lookup_named_location(location_name)
            if location is None:
                return None

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

    def _resolve_location(self, prompt: str, meta: dict[str, Any]) -> ResolvedLocation | str | None:
        """Resolve a weather target from the prompt or saved session metadata."""
        explicit_location = self._extract_explicit_location(prompt)
        if explicit_location:
            return explicit_location

        home_location = self._home_location()
        if home_location is not None:
            return home_location

        return self._config_mgr.config_value("weather", "default_location", default="").strip() or None

    def _lookup_named_location(
        self,
        location_name: str,
    ) -> ResolvedLocation | None:
        """Resolve a plain-text location name, preferring nearby candidates when ambiguous."""
        candidates = self._location_lookup_candidates(location_name)
        home_location = self._home_location()
        seen: set[str] = set()
        for candidate in candidates:
            normalized_candidate = candidate.strip()
            if not normalized_candidate:
                continue
            dedupe_key = normalized_candidate.lower()
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            try:
                locations = self._provider.search_locations(normalized_candidate, limit=10)
            except Exception as exc:
                self._logger.log_error(
                    f"Weather plugin location lookup failed for '{normalized_candidate}': {exc}"
                )
                return None
            location = self._best_location_match(locations, normalized_candidate, home_location)
            if location is not None:
                return location
        return None

    def _location_lookup_candidates(self, location_name: str) -> list[str]:
        """Return lookup candidates from most specific to more forgiving variants."""
        normalized_name = str(location_name or "").strip(" ?.!,")
        if not normalized_name:
            return []

        candidates = [normalized_name]
        country_hint = self._country_hint_from_home_location(self._home_location())
        if country_hint and "," not in normalized_name:
            candidates.append(f"{normalized_name}, {country_hint}")

        parts = [part.strip() for part in normalized_name.split(",") if part.strip()]
        if len(parts) > 1:
            primary = parts[0]
            qualifiers = parts[1:]
            candidates.append(primary)
            if country_hint:
                candidates.append(f"{primary}, {country_hint}")
            for qualifier in qualifiers:
                candidates.append(f"{primary}, {qualifier}")

        return candidates

    @staticmethod
    def _resolved_location_from_meta(
        user_location_pref: dict[str, Any] | None,
    ) -> ResolvedLocation | None:
        """Build a resolved location directly from the saved user preference payload."""
        if not isinstance(user_location_pref, dict):
            return None

        name = str(user_location_pref.get("name") or "").strip()
        timezone_name = str(user_location_pref.get("timezone") or "").strip()
        if not name or not timezone_name:
            return None

        try:
            latitude = float(user_location_pref.get("latitude"))
            longitude = float(user_location_pref.get("longitude"))
        except (TypeError, ValueError):
            return None

        country = str(user_location_pref.get("country") or "").strip() or None
        admin1 = str(user_location_pref.get("admin1") or "").strip() or None
        return ResolvedLocation(
            name=name,
            latitude=latitude,
            longitude=longitude,
            timezone=timezone_name,
            country=country,
            admin1=admin1,
        )

    @staticmethod
    def _country_hint_from_home_location(home_location: ResolvedLocation | None) -> str | None:
        """Return a country hint from the saved user location when available."""
        if home_location is None:
            return None
        country = str(home_location.country or "").strip()
        return country or None

    def _home_location(self) -> ResolvedLocation | None:
        """Return the saved user location through the entitlement-checked data API."""
        if self._data_access is None:
            return None
        user_location_pref = self._data_access.get("user_preferences.user_location")
        return self._resolved_location_from_meta(user_location_pref)

    @staticmethod
    def _best_location_match(
        locations: tuple[ResolvedLocation, ...],
        requested_name: str,
        home_location: ResolvedLocation | None,
    ) -> ResolvedLocation | None:
        """Choose the best location candidate for an explicit weather query."""
        if not locations:
            return None

        requested_parts = [
            part.strip().lower()
            for part in str(requested_name or "").split(",")
            if part.strip()
        ]
        primary_name = requested_parts[0] if requested_parts else ""
        qualifier_parts = requested_parts[1:]
        normalized_qualifiers = {
            part
            for part in qualifier_parts
            if part not in {"england", "united kingdom", "great britain", "uk"}
        }

        matching_name_locations = tuple(
            location
            for location in locations
            if location.name.strip().lower() == primary_name
        ) or locations

        if normalized_qualifiers:
            qualified_matches = tuple(
                location
                for location in matching_name_locations
                if WeatherPlugin._location_matches_qualifiers(location, normalized_qualifiers)
            )
            if qualified_matches:
                matching_name_locations = qualified_matches

        if " " in primary_name:
            return matching_name_locations[0]

        if home_location is None or len(matching_name_locations) == 1:
            return matching_name_locations[0]

        return min(
            matching_name_locations,
            key=lambda location: WeatherPlugin._distance_score(home_location, location),
        )

    @staticmethod
    def _location_matches_qualifiers(
        location: ResolvedLocation,
        qualifiers: set[str],
    ) -> bool:
        """Return whether a geocoded location matches all non-country qualifiers."""
        candidate_parts = {
            str(location.admin1 or "").strip().lower(),
            str(location.country or "").strip().lower(),
            str(location.name or "").strip().lower(),
        }
        candidate_parts.discard("")
        return qualifiers.issubset(candidate_parts)

    @staticmethod
    def _distance_score(
        origin: ResolvedLocation,
        candidate: ResolvedLocation,
    ) -> float:
        """Return an approximate squared distance between two locations."""
        lat_delta = origin.latitude - candidate.latitude
        lon_delta = origin.longitude - candidate.longitude
        return math.pow(lat_delta, 2) + math.pow(lon_delta, 2)

    @staticmethod
    def _extract_explicit_location(prompt: str) -> str | None:
        patterns = [
            r"\bweather in ([A-Za-z][A-Za-z ,.'\-]+)",
            r"\btemperature in ([A-Za-z][A-Za-z ,.'\-]+)",
            r"\bforecast for ([A-Za-z][A-Za-z ,.'\-]+)",
            r"\bin ([A-Za-z][A-Za-z ,.'\-]+)\??$",
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
