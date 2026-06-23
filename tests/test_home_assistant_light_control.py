"""Tests for deterministic Home Assistant light-control parsing and planning."""
# Author: Clive Bostock
# Date: 12-Jun-2026
# Description: Verifies rich light parsing, capability checks, and live-state planning.

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

from home_assistant.light_control import LightControlError
from home_assistant.light_control import build_light_service_data
from home_assistant.light_control import parse_light_control_command


def _state(**attributes) -> dict:
    return {
        "entity_id": "light.tv_light",
        "state": "on",
        "attributes": attributes,
    }


class HomeAssistantLightControlTests(unittest.TestCase):
    """Tests rich light-control parsing and live capability validation."""

    def test_parser_maps_brightness_colour_and_temperature_commands(self) -> None:
        cases = {
            "Set the TV light to 50 percent.": ("brightness_pct", 50, "tv light"),
            "Dim the TV light": ("brightness_step", -10, "tv light"),
            "Brighten the TV light": ("brightness_step", 10, "tv light"),
            "Set the TV light to blue": ("color_name", "blue", "tv light"),
            "Make the lounge light toasty": ("color_temp_kelvin", 2700, "lounge light"),
            "Reset the TV light to normal white": (
                "color_temp_kelvin",
                4000,
                "tv light",
            ),
        }
        for prompt, expected in cases.items():
            with self.subTest(prompt=prompt):
                request = parse_light_control_command(prompt)
                self.assertIsNotNone(request)
                self.assertEqual((request.kind, request.value, request.target), expected)

    def test_absolute_brightness_uses_requested_percent(self) -> None:
        request = parse_light_control_command("Set the TV light to 50 percent")
        payload, response = build_light_service_data(
            request,
            _state(supported_color_modes=["brightness"], brightness=128),
            target_label="TV light",
        )

        self.assertEqual(payload, {"brightness_pct": 50})
        self.assertEqual(response, "TV light set to 50 percent.")

    def test_relative_brightness_uses_live_brightness_and_clamps(self) -> None:
        request = parse_light_control_command("Dim the TV light")
        payload, response = build_light_service_data(
            request,
            _state(supported_color_modes=["brightness"], brightness=76),
            target_label="TV light",
        )

        self.assertEqual(payload, {"brightness_pct": 20})
        self.assertEqual(response, "TV light dimmed to 20 percent.")

    def test_colour_name_is_validated_against_allowlist(self) -> None:
        request = parse_light_control_command("Set the TV light to blue")
        payload, response = build_light_service_data(
            request,
            _state(supported_color_modes=["hs"], hs_color=[210.0, 100.0]),
            target_label="TV light",
        )

        self.assertEqual(payload, {"color_name": "blue"})
        self.assertEqual(response, "TV light set to blue.")

    def test_colour_name_rejects_unsupported_light_capabilities(self) -> None:
        request = parse_light_control_command("Set the TV light to blue")

        with self.assertRaisesRegex(LightControlError, "colour control"):
            build_light_service_data(
                request,
                _state(supported_color_modes=["brightness"], brightness=128),
                target_label="TV light",
            )

    def test_colour_temperature_uses_live_state_and_clamps(self) -> None:
        request = parse_light_control_command("Make the lounge light warmer")
        payload, response = build_light_service_data(
            request,
            _state(
                supported_color_modes=["color_temp"],
                color_temp_kelvin=3000,
                min_color_temp_kelvin=2700,
                max_color_temp_kelvin=6500,
            ),
            target_label="Lounge light",
        )

        self.assertEqual(payload, {"color_temp_kelvin": 2700})
        self.assertEqual(response, "Lounge light set to warm white.")

    def test_colour_temperature_rejects_switch_off_state_without_support(self) -> None:
        request = parse_light_control_command("Set the TV light to 2700 Kelvin")

        with self.assertRaisesRegex(LightControlError, "colour temperature"):
            build_light_service_data(
                request,
                _state(supported_color_modes=["brightness"], brightness=128),
                target_label="TV light",
            )

    def test_invalid_brightness_percent_is_refused(self) -> None:
        request = parse_light_control_command("Set the TV light to 101 percent")
        self.assertIsNotNone(request)

        with self.assertRaisesRegex(LightControlError, "between 1 and 100"):
            build_light_service_data(
                request,
                _state(supported_color_modes=["brightness"], brightness=128),
                target_label="TV light",
            )


if __name__ == "__main__":
    unittest.main()
