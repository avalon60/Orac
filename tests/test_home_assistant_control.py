"""Tests for deterministic Home Assistant control parsing and resolution."""
# Author: Clive Bostock
# Date: 11-Jun-2026
# Description: Verifies low-risk action mapping and exact target resolution.

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

from home_assistant.control import HomeAssistantControlError
from home_assistant.control import parse_control_command
from home_assistant.control import resolve_control_target


def _row(entity_id: str, **overrides) -> dict:
    domain, object_id = entity_id.split(".", 1)
    row = {
        "alias_name": None,
        "entity_id": entity_id,
        "domain": domain,
        "object_id": object_id,
        "entity_name": None,
        "original_name": None,
        "friendly_name": None,
        "device_name": None,
        "area_name": None,
        "area_aliases": None,
        "current_state": "off",
    }
    row.update(overrides)
    return row


class HomeAssistantControlTests(unittest.TestCase):
    """Tests parser allowlists and resolver precedence."""

    def test_parser_maps_supported_light_switch_and_scene_actions(self) -> None:
        cases = {
            "Turn on the kitchen lights": ("turn_on", "kitchen lights", "light"),
            "Switch off office lamp": ("turn_off", "office lamp", "light"),
            "Switch office lamp off.": ("turn_off", "office lamp", "light"),
            "Turn the desk lamp on": ("turn_on", "desk lamp", "light"),
            "Off the desk lamp.": ("turn_off", "desk lamp", "light"),
            "Toggle desk switch": ("toggle", "desk switch", "switch"),
            "Activate movie night": ("activate", "movie night", "scene"),
            "Turn on scene movie night": ("activate", "movie night", "scene"),
        }
        for prompt, expected in cases.items():
            with self.subTest(prompt=prompt):
                request = parse_control_command(prompt)
                self.assertIsNotNone(request)
                self.assertEqual(
                    (request.action, request.target, request.requested_domain),
                    expected,
                )

    def test_parser_ignores_non_control_phrases(self) -> None:
        self.assertIsNone(parse_control_command("Is the kitchen light on?"))
        self.assertIsNone(parse_control_command("Sync devices"))

    def test_parser_refuses_whole_home_commands(self) -> None:
        with self.assertRaisesRegex(HomeAssistantControlError, "Whole-home"):
            parse_control_command("Turn off all lights")

    def test_alias_precedes_an_exact_entity_name_and_supports_groups(self) -> None:
        rows = [
            _row(
                "light.kitchen_one",
                alias_name="downstairs",
                friendly_name="downstairs",
            ),
            _row("light.kitchen_two", alias_name="downstairs"),
        ]
        request = parse_control_command("Turn on downstairs")

        resolved = resolve_control_target(request, rows)

        self.assertEqual(resolved.resolution, "alias")
        self.assertEqual(
            resolved.entity_ids,
            ("light.kitchen_one", "light.kitchen_two"),
        )

    def test_alias_group_refuses_incompatible_or_blocked_members(self) -> None:
        request = parse_control_command("Turn on downstairs lights")
        with self.assertRaisesRegex(HomeAssistantControlError, "incompatible"):
            resolve_control_target(
                request,
                [
                    _row("light.kitchen", alias_name="downstairs lights"),
                    _row("switch.router", alias_name="downstairs lights"),
                ],
            )
        with self.assertRaisesRegex(HomeAssistantControlError, "not allowed"):
            resolve_control_target(
                request,
                [
                    _row("light.kitchen", alias_name="downstairs lights"),
                    _row("lock.front_door", alias_name="downstairs lights"),
                ],
            )

    def test_disabled_alias_is_not_considered(self) -> None:
        rows = [_row("light.office", alias_name=None, friendly_name="office lamp")]
        request = parse_control_command("Turn on work light")

        with self.assertRaisesRegex(HomeAssistantControlError, "not found"):
            resolve_control_target(request, rows)

    def test_exact_entity_id_object_id_and_names_resolve(self) -> None:
        row = _row(
            "light.office_lamp",
            entity_name="Office Lamp",
            original_name="Desk Light",
            friendly_name="Work Lamp",
            device_name="Office Lighting",
        )
        for target in (
            "light.office_lamp",
            "office_lamp",
            "office lamp",
            "desk light",
            "work lamp",
            "office lighting",
        ):
            with self.subTest(target=target):
                request = parse_control_command(f"Turn on {target}")
                resolved = resolve_control_target(request, [row])
                self.assertEqual(resolved.entity_ids, ("light.office_lamp",))

    def test_exact_duplicate_names_are_ambiguous(self) -> None:
        rows = [
            _row("light.one", friendly_name="Reading Lamp"),
            _row("light.two", friendly_name="Reading Lamp"),
        ]
        request = parse_control_command("Turn on reading lamp")

        with self.assertRaisesRegex(HomeAssistantControlError, "ambiguous"):
            resolve_control_target(request, rows)

    def test_named_area_and_area_alias_resolve_groups(self) -> None:
        rows = [
            _row("light.kitchen", area_name="Kitchen", area_aliases='["Galley"]'),
            _row(
                "switch.kitchen_lamp",
                friendly_name="Kitchen Lamp",
                area_name="Kitchen",
                area_aliases='["Galley"]',
            ),
        ]
        for prompt in ("Turn on kitchen lights", "Turn on galley lights"):
            with self.subTest(prompt=prompt):
                resolved = resolve_control_target(parse_control_command(prompt), rows)
                self.assertEqual(resolved.resolution, "area")
                self.assertEqual(len(resolved.service_calls), 2)

    def test_switch_backed_lamp_accepts_light_terminology(self) -> None:
        rows = [_row("switch.floor_lamp", friendly_name="Floor Lamp")]
        request = parse_control_command("Turn on floor lamp")

        resolved = resolve_control_target(request, rows)

        self.assertEqual(resolved.service_calls[0].domain, "switch")
        self.assertEqual(resolved.service_calls[0].service, "turn_on")

    def test_switch_backed_lamp_ignores_same_device_child_entities(self) -> None:
        rows = [
            _row(
                "switch.desk_lamp",
                friendly_name="Desk Lamp",
                device_name="Desk Lamp",
            ),
            _row(
                "sensor.desk_lamp_power",
                friendly_name="Desk Lamp Power",
                device_name="Desk Lamp",
            ),
            _row(
                "button.desk_lamp_identify",
                friendly_name="Desk Lamp Identify",
                device_name="Desk Lamp",
            ),
            _row(
                "update.desk_lamp_firmware",
                friendly_name="Desk Lamp Firmware",
                device_name="Desk Lamp",
            ),
        ]

        resolved = resolve_control_target(
            parse_control_command("Turn off desk lamp"),
            rows,
        )

        self.assertEqual(resolved.entity_ids, ("switch.desk_lamp",))
        self.assertEqual(resolved.service_calls[0].service, "turn_off")

    def test_scene_maps_activation_to_scene_turn_on(self) -> None:
        rows = [_row("scene.movie_night", friendly_name="Movie Night")]
        request = parse_control_command("Activate movie night")

        resolved = resolve_control_target(request, rows)

        self.assertEqual(resolved.service_calls[0].domain, "scene")
        self.assertEqual(resolved.service_calls[0].service, "turn_on")

    def test_blocked_domain_and_unsupported_combination_are_refused(self) -> None:
        with self.assertRaisesRegex(HomeAssistantControlError, "not allowed"):
            resolve_control_target(
                parse_control_command("Turn on front door lock"),
                [_row("lock.front_door", friendly_name="Front Door Lock")],
            )
        with self.assertRaisesRegex(HomeAssistantControlError, "not supported"):
            resolve_control_target(
                parse_control_command("Toggle movie night"),
                [_row("scene.movie_night", friendly_name="Movie Night")],
            )

    def test_unknown_target_is_refused(self) -> None:
        with self.assertRaisesRegex(HomeAssistantControlError, "not found"):
            resolve_control_target(
                parse_control_command("Turn on missing lamp"),
                [_row("light.office", friendly_name="Office Lamp")],
            )


if __name__ == "__main__":
    unittest.main()
