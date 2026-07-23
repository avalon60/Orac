"""Dialogue interceptor for Weather plugin routing."""
# Author: Clive Bostock
# Date: 17-Jul-2026
# Description: Maps Weather dialogue metadata matches into route arguments.

from __future__ import annotations

from typing import Any, Mapping

from model.plugin_routing.interception import InterceptRule, PluginDialogInterceptor


_INDOOR_TEMPERATURE_TARGETS = {
    "bathroom",
    "bedroom",
    "hall",
    "hallway",
    "kitchen",
    "landing",
    "lounge",
    "office",
    "room",
    "study",
}


class WeatherDialogInterceptor(PluginDialogInterceptor):
    """Build Weather route arguments from core-owned metadata matches."""

    def build_arguments(
        self,
        *,
        rule: InterceptRule,
        captures: Mapping[str, str],
        original_text: str,
        normalised_text: str,
    ) -> Mapping[str, Any] | None:
        """Return Weather route arguments or reject indoor temperature wording."""
        arguments: dict[str, Any] = dict(rule.arguments)
        arguments.update(
            {
                key: value.strip()
                for key, value in captures.items()
                if str(value).strip()
            }
        )
        if _looks_like_indoor_temperature(arguments, normalised_text):
            return None
        return arguments


def _looks_like_indoor_temperature(
    arguments: Mapping[str, Any],
    normalised_text: str,
) -> bool:
    """Return whether Weather should defer indoor sensor-style temperature text."""
    if str(arguments.get("response_type") or "").strip() != "temperature":
        return False
    location = str(arguments.get("location") or "").casefold().strip()
    if location and any(token in location.split() for token in _INDOOR_TEMPERATURE_TARGETS):
        return True
    if any(
        normalised_text == f"what is the {target} temperature"
        or normalised_text == f"what's the {target} temperature"
        for target in _INDOOR_TEMPERATURE_TARGETS
    ):
        return True
    return False
