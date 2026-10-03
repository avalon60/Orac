"""Tests generic Home Assistant capability derivation."""
# Author: Clive Bostock
# Date: 11-Sep-2026
# Description: Verifies entity-first primitive discovery without vendor rules.

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

from home_assistant.capabilities import PrimitiveCapability
from home_assistant.capabilities import derive_capability_snapshot
from home_assistant.capabilities import prepare_capability_operation
from home_assistant.capabilities import update_capability_state


class HomeAssistantCapabilityTests(unittest.TestCase):
    """Tests generic capability and device composition contracts."""

    def test_standard_entities_derive_without_manufacturer_or_model(self) -> None:
        entities = [
            {"entity_id": "light.desk", "device_id": "device-1", "platform": "new_vendor"},
            {"entity_id": "sensor.desk_temperature", "device_id": "device-1"},
        ]
        states = [
            {
                "entity_id": "light.desk",
                "state": "off",
                "attributes": {
                    "supported_color_modes": ["rgb", "color_temp"],
                    "min_color_temp_kelvin": 2000,
                    "max_color_temp_kelvin": 6500,
                },
            },
            {
                "entity_id": "sensor.desk_temperature",
                "state": "20.1",
                "attributes": {"device_class": "temperature", "unit_of_measurement": "°C"},
            },
        ]
        services = {
            "light": {"turn_on": {"fields": {}}, "turn_off": {"fields": {}}}
        }

        snapshot = derive_capability_snapshot(
            entities,
            states,
            services,
            devices=[{
                "id": "device-1",
                "name": "Desk unit",
                "area_id": "office",
                "manufacturer": "new_vendor",
                "model": "never-seen-before",
            }],
        )

        primitives = {item.primitive for item in snapshot.bindings["light.desk"]}
        self.assertEqual(
            primitives,
            {
                PrimitiveCapability.READ_STATE,
                PrimitiveCapability.TURN_ON,
                PrimitiveCapability.TURN_OFF,
                PrimitiveCapability.SET_LEVEL,
                PrimitiveCapability.SET_COLOUR,
                PrimitiveCapability.SET_COLOUR_TEMPERATURE,
            },
        )
        self.assertEqual(
            snapshot.devices["device-1"].capabilities[PrimitiveCapability.READ_STATE],
            ("light.desk", "sensor.desk_temperature"),
        )
        self.assertEqual(snapshot.devices["device-1"].name, "Desk unit")
        self.assertEqual(snapshot.devices["device-1"].area_id, "office")
        self.assertEqual(snapshot.entities["light.desk"].area_id, "office")

    def test_target_service_filter_applies_per_entity(self) -> None:
        services = {"cover": {"open_cover": {}, "set_cover_position": {}}}
        snapshot = derive_capability_snapshot(
            [{"entity_id": "cover.garage"}],
            [{"entity_id": "cover.garage", "state": "closed", "attributes": {}}],
            services,
            services_by_entity={"cover.garage": ["cover.open_cover"]},
        )

        primitives = {item.primitive for item in snapshot.bindings["cover.garage"]}
        self.assertIn(PrimitiveCapability.OPEN, primitives)
        self.assertNotIn(PrimitiveCapability.SET_POSITION, primitives)

    def test_target_metadata_promotes_canonical_custom_integration_action(self) -> None:
        snapshot = derive_capability_snapshot(
            [{"entity_id": "new_platform.awning"}],
            [{
                "entity_id": "new_platform.awning",
                "state": "closed",
                "attributes": {},
            }],
            {
                "vendor_bridge": {
                    "open": {"fields": {}},
                    "calibrate_motor": {"fields": {"mode": {}}},
                }
            },
            services_by_entity={
                "new_platform.awning": [
                    "vendor_bridge.open",
                    "vendor_bridge.calibrate_motor",
                ]
            },
        )

        bindings = snapshot.bindings["new_platform.awning"]
        self.assertIn(
            (PrimitiveCapability.OPEN, "vendor_bridge.open"),
            {(binding.primitive, binding.action_id) for binding in bindings},
        )
        self.assertNotIn("vendor_bridge.calibrate_motor", {
            binding.action_id for binding in bindings
        })

    def test_custom_parameter_action_requires_described_service_field(self) -> None:
        snapshot = derive_capability_snapshot(
            [{"entity_id": "new_platform.level"}],
            [{
                "entity_id": "new_platform.level",
                "state": "50",
                "attributes": {},
            }],
            {"vendor_bridge": {"set_percentage": {"fields": {}}}},
            services_by_entity={
                "new_platform.level": ["vendor_bridge.set_percentage"]
            },
        )

        self.assertEqual(
            [
                binding.primitive
                for binding in snapshot.bindings["new_platform.level"]
            ],
            [PrimitiveCapability.READ_STATE],
        )

    def test_supported_features_is_conservative_without_target_discovery(self) -> None:
        snapshot = derive_capability_snapshot(
            [{"entity_id": "cover.garage"}],
            [
                {
                    "entity_id": "cover.garage",
                    "state": "closed",
                    "attributes": {"supported_features": 3},
                }
            ],
            {
                "cover": {
                    "open_cover": {},
                    "close_cover": {},
                    "stop_cover": {},
                    "set_cover_position": {},
                }
            },
        )

        primitives = {item.primitive for item in snapshot.bindings["cover.garage"]}
        self.assertTrue(
            {PrimitiveCapability.OPEN, PrimitiveCapability.CLOSE} <= primitives
        )
        self.assertNotIn(PrimitiveCapability.STOP, primitives)
        self.assertNotIn(PrimitiveCapability.SET_POSITION, primitives)

    def test_state_only_entity_remains_readable_inventory(self) -> None:
        snapshot = derive_capability_snapshot(
            [],
            [{"entity_id": "sensor.unregistered", "state": "ok", "attributes": {}}],
            {},
        )

        self.assertIn("sensor.unregistered", snapshot.entities)
        self.assertEqual(
            snapshot.bindings["sensor.unregistered"][0].primitive,
            PrimitiveCapability.READ_STATE,
        )

    def test_manufacturer_metadata_does_not_change_generation(self) -> None:
        state = [{"entity_id": "switch.plug", "state": "on", "attributes": {}}]
        services = {"switch": {"turn_on": {}, "turn_off": {}}}
        first = derive_capability_snapshot(
            [{"entity_id": "switch.plug", "manufacturer": "A", "model": "One"}],
            state,
            services,
        )
        second = derive_capability_snapshot(
            [{"entity_id": "switch.plug", "manufacturer": "B", "model": "Two"}],
            state,
            services,
        )

        self.assertEqual(first.generation, second.generation)

    def test_prepares_service_data_from_derived_binding(self) -> None:
        snapshot = derive_capability_snapshot(
            [{"entity_id": "light.unfamiliar", "device_id": "device-1"}],
            [{
                "entity_id": "light.unfamiliar",
                "state": "on",
                "attributes": {"supported_color_modes": ["rgb"]},
            }],
            {"light": {"turn_on": {"fields": {}}}},
        )

        operation = prepare_capability_operation(
            snapshot,
            "device-1",
            PrimitiveCapability.SET_LEVEL,
            {"percent": 42},
        )[0]

        self.assertEqual(operation.action_id, "light.turn_on")
        self.assertEqual(operation.entity_ids, ("light.unfamiliar",))
        self.assertEqual(operation.service_data, {"brightness_pct": 42})

    def test_rejects_invalid_or_model_supplied_parameters(self) -> None:
        snapshot = derive_capability_snapshot(
            [{"entity_id": "light.unfamiliar"}],
            [{
                "entity_id": "light.unfamiliar",
                "state": "on",
                "attributes": {"supported_color_modes": ["brightness"]},
            }],
            {"light": {"turn_on": {"fields": {}}}},
        )

        with self.assertRaisesRegex(ValueError, "above maximum"):
            prepare_capability_operation(
                snapshot,
                "light.unfamiliar",
                "set_level",
                {"percent": 101},
            )
        with self.assertRaisesRegex(ValueError, "unexpected"):
            prepare_capability_operation(
                snapshot,
                "light.unfamiliar",
                "set_level",
                {"percent": 50, "service": "unlock"},
            )

    def test_rejects_out_of_range_colour_components(self) -> None:
        snapshot = derive_capability_snapshot(
            [{"entity_id": "light.unfamiliar"}],
            [{
                "entity_id": "light.unfamiliar",
                "state": "on",
                "attributes": {"supported_color_modes": ["rgb"]},
            }],
            {"light": {"turn_on": {}}},
        )

        with self.assertRaisesRegex(ValueError, r"rgb\[2\].*above maximum"):
            prepare_capability_operation(
                snapshot,
                "light.unfamiliar",
                "set_colour",
                {"rgb": [12, 34, 300]},
            )

    def test_state_event_publishes_new_generation_and_availability(self) -> None:
        snapshot = derive_capability_snapshot(
            [{"entity_id": "switch.plug", "device_id": "plug-device"}],
            [{"entity_id": "switch.plug", "state": "on", "attributes": {}}],
            {"switch": {"turn_on": {}, "turn_off": {}}},
            services_by_entity={
                "switch.plug": ["switch.turn_on", "switch.turn_off"]
            },
            devices=[{"id": "plug-device", "name": "Desk plug"}],
        )

        updated = update_capability_state(
            snapshot,
            {"entity_id": "switch.plug", "state": "unavailable", "attributes": {}},
        )

        self.assertNotEqual(updated.generation, snapshot.generation)
        controls = [
            binding
            for binding in updated.bindings["switch.plug"]
            if binding.action_id is not None
        ]
        self.assertTrue(controls)
        self.assertTrue(all(not binding.available for binding in controls))
        self.assertEqual(updated.devices["plug-device"].name, "Desk plug")

    def test_representative_fixture_covers_unowned_and_unusual_devices(self) -> None:
        fixture = json.loads(
            (
                PROJECT_ROOT
                / "tests"
                / "fixtures"
                / "home_assistant"
                / "representative_capabilities.json"
            ).read_text(encoding="utf-8")
        )

        snapshot = derive_capability_snapshot(
            fixture["entities"],
            fixture["states"],
            fixture["services"],
            services_by_entity=fixture["services_by_entity"],
        )

        expected = {
            "cover.unknown_blind": {"open", "close", "stop", "set_position"},
            "climate.heat_pump": {"set_temperature"},
            "lock.front_door": {"lock", "unlock"},
            "media_player.receiver": {"play", "pause", "set_volume"},
            "number.charge_limit": {"set_value"},
            "select.operating_mode": {"select_option"},
        }
        for entity_id, primitives in expected.items():
            with self.subTest(entity_id=entity_id):
                actual = {
                    binding.primitive.value
                    for binding in snapshot.bindings[entity_id]
                    if binding.action_id is not None
                }
                self.assertEqual(actual, primitives)
        self.assertEqual(
            snapshot.devices["device-window"].entity_ids,
            ("cover.unknown_blind", "sensor.unknown_battery"),
        )


if __name__ == "__main__":
    unittest.main()
