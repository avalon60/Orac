"""Tests for deterministic Home Assistant live light-state parsing and rendering."""
# Author: Clive Bostock
# Date: 12-Jun-2026
# Description: Verifies live light read-back parsing and response shaping.

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

from home_assistant.color_description import describe_rgb_color
from home_assistant.light_state_query import LightStateQueryError
from home_assistant.light_state_query import parse_light_state_query
from home_assistant.light_state_query import render_light_state_query


def _state(entity_id: str, state: str, **attributes) -> dict:
    return {
        "entity_id": entity_id,
        "state": state,
        "attributes": attributes,
    }


class HomeAssistantLightStateQueryTests(unittest.TestCase):
    """Tests live light-state parsing and rendering."""

    def test_parser_maps_entity_and_area_queries(self) -> None:
        cases = {
            "Is the TV light on?": ("state", "tv light", "entity"),
            "How bright is the TV light?": ("brightness", "tv light", "entity"),
            "What colour is the TV light?": ("color", "tv light", "entity"),
            "Are any lounge lights on?": ("area_any_on", "lounge", "area"),
            "Which lounge lights are on?": ("area_list_on", "lounge", "area"),
            "Are all lounge lights off?": ("area_all_off", "lounge", "area"),
            "Is the TV light warm white?": (
                "color_temperature_check",
                "tv light",
                "entity",
            ),
        }
        for prompt, expected in cases.items():
            with self.subTest(prompt=prompt):
                request = parse_light_state_query(prompt)
                self.assertIsNotNone(request)
                self.assertEqual((request.intent, request.target, request.scope), expected)

    def test_render_reports_live_brightness_and_last_known_off_setting(self) -> None:
        result = render_light_state_query(
            parse_light_state_query("How bright is the TV light?"),
            [
                _state(
                    "light.tv_light",
                    "off",
                    friendly_name="TV Light",
                    brightness=107,
                )
            ],
        )

        self.assertIn("off", result.content)
        self.assertIn("last-known brightness setting is 42 percent", result.content)

    def test_render_reports_colour_temperature_and_warm_white_check(self) -> None:
        result = render_light_state_query(
            parse_light_state_query("Is the TV light warm white?"),
            [
                _state(
                    "light.tv_light",
                    "on",
                    friendly_name="TV Light",
                    color_temp_kelvin=2700,
                )
            ],
        )

        self.assertIn("warm white", result.content)
        self.assertIn("2700 Kelvin", result.content)

    def test_rgb_colour_descriptions_cover_common_values(self) -> None:
        cases = {
            (255, 237, 222): "warm off-white / pale cream",
            (255, 0, 0): "bright red",
            (0, 255, 255): "bright cyan",
            (0, 0, 255): "bright blue",
            (255, 255, 255): "white",
            (180, 180, 180): "grey",
            (255, 220, 180): "warm cream / pale peach",
        }
        for rgb, expected in cases.items():
            with self.subTest(rgb=rgb):
                self.assertEqual(describe_rgb_color(rgb), expected)

    def test_low_saturation_warm_rgb_is_not_reported_as_orange(self) -> None:
        self.assertEqual(describe_rgb_color((255, 220, 180)), "warm cream / pale peach")

    def test_render_includes_colour_description_and_raw_rgb(self) -> None:
        result = render_light_state_query(
            parse_light_state_query("What colour is the TV light?"),
            [
                _state(
                    "light.tv_light",
                    "on",
                    friendly_name="TV Light",
                    rgb_color=(255, 237, 222),
                )
            ],
        )

        self.assertIn("roughly a warm off-white / pale cream colour", result.content)
        self.assertIn("RGB values 255, 237, 222", result.content)

    def test_render_falls_back_cleanly_when_rgb_missing(self) -> None:
        result = render_light_state_query(
            parse_light_state_query("What colour is the TV light?"),
            [
                _state(
                    "light.tv_light",
                    "on",
                    friendly_name="TV Light",
                )
            ],
        )

        self.assertEqual(
            result.content,
            "Home Assistant is not exposing a current colour setting for the TV Light.",
        )

    def test_render_summarises_area_states_from_live_data(self) -> None:
        result = render_light_state_query(
            parse_light_state_query("Are any lounge lights on?"),
            [
                _state("light.tv_light", "on", friendly_name="TV Light"),
                _state("light.floor_lamp", "on", friendly_name="Floor Lamp"),
                _state("switch.corner_lamp", "off", friendly_name="Corner Lamp"),
            ],
        )

        self.assertIn("2 Lounge lights are on", result.content)
        self.assertIn("TV Light and Floor Lamp", result.content)
        self.assertIn("Corner Lamp", result.content)

    def test_render_refuses_unknown_targets(self) -> None:
        with self.assertRaises(LightStateQueryError):
            render_light_state_query(
                parse_light_state_query("Is the TV light on?"),
                [],
            )


if __name__ == "__main__":
    unittest.main()
