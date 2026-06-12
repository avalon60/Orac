"""Tests for deterministic Home Assistant temperature and humidity queries."""
# Author: Clive Bostock
# Date: 12-Jun-2026
# Description: Verifies read-only sensor parsing, classification, resolution, and responses.

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
if str(PLUGINS_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGINS_ROOT))

from home_assistant.sensor_query import HomeAssistantSensorQueryError
from home_assistant.sensor_query import classify_sensor_role
from home_assistant.sensor_query import execute_sensor_query
from home_assistant.sensor_query import interpret_humidity
from home_assistant.sensor_query import interpret_temperature
from home_assistant.sensor_query import parse_sensor_query


NOW = datetime(2026, 6, 12, 12, 0, tzinfo=UTC)


def _sensor(
    entity_id: str,
    *,
    area: str,
    state: str,
    device_class: str | None = None,
    unit: str | None = None,
    updated: datetime | None = None,
    aliases: str | None = None,
    disabled_by: str | None = None,
) -> dict:
    """Build one resolution-view sensor row for tests."""
    return {
        "entity_id": entity_id,
        "domain": "sensor",
        "object_id": entity_id.split(".", 1)[1],
        "friendly_name": entity_id.split(".", 1)[1].replace("_", " "),
        "area_name": area,
        "area_aliases": aliases,
        "current_state": state,
        "device_class": device_class,
        "unit_of_measurement": unit,
        "last_updated": updated or NOW - timedelta(minutes=12),
        "last_changed": updated or NOW - timedelta(minutes=12),
        "disabled_by": disabled_by,
    }


class HomeAssistantSensorQueryTests(unittest.TestCase):
    """Tests the deterministic read-only sensor query implementation."""

    def test_parser_maps_supported_query_intents(self) -> None:
        cases = {
            "What's the temperature in the lounge?": (
                "area_temperature",
                ("lounge",),
            ),
            "What is the landing temperature?": (
                "area_temperature",
                ("landing",),
            ),
            "What's the living room temperature?": (
                "area_temperature",
                ("living room",),
            ),
            "What's the humidity on the landing?": (
                "area_humidity",
                ("landing",),
            ),
            "What is the landing humidity?": (
                "area_humidity",
                ("landing",),
            ),
            "How humid is the landing?": ("area_humidity", ("landing",)),
            "Is the lounge humid?": ("area_humidity", ("lounge",)),
            "What's the temperature and humidity in the lounge?": (
                "area_climate_summary",
                ("lounge",),
            ),
            "Which is warmer, the lounge or the landing?": (
                "compare_area_temperature",
                ("lounge", "landing"),
            ),
            "Are any sensors unavailable?": ("sensor_availability", ()),
            "When was the lounge sensor last updated?": (
                "sensor_freshness",
                ("lounge",),
            ),
        }
        for prompt, expected in cases.items():
            with self.subTest(prompt=prompt):
                request = parse_sensor_query(prompt)
                self.assertIsNotNone(request)
                self.assertEqual((request.intent, request.areas), expected)

    def test_sensor_role_classification_uses_metadata_then_safe_names(self) -> None:
        self.assertEqual(
            classify_sensor_role({"device_class": "temperature"}),
            "temperature",
        )
        self.assertEqual(
            classify_sensor_role({"device_class": "humidity"}),
            "humidity",
        )
        self.assertEqual(
            classify_sensor_role({"device_class": "battery"}),
            "battery",
        )
        self.assertEqual(
            classify_sensor_role({"unit_of_measurement": "°C"}),
            "temperature",
        )
        self.assertEqual(
            classify_sensor_role({"entity_id": "sensor.lounge_humidity"}),
            "humidity",
        )
        self.assertEqual(
            classify_sensor_role({"unit_of_measurement": "%"}),
            "unknown",
        )

    def test_temperature_query_returns_value_unit_interpretation_and_age(self) -> None:
        result = execute_sensor_query(
            parse_sensor_query("What's the temperature in the lounge?"),
            [
                _sensor(
                    "sensor.lounge_temperature",
                    area="Lounge",
                    state="21.4",
                    device_class="temperature",
                    unit="°C",
                )
            ],
            now=NOW,
        )

        self.assertIn("Lounge temperature is 21.4°C", result.content)
        self.assertIn("comfortable", result.content)
        self.assertIn("12 minutes ago", result.content)

    def test_humidity_query_resolves_area_alias_and_interprets_value(self) -> None:
        result = execute_sensor_query(
            parse_sensor_query("How humid is the front room?"),
            [
                _sensor(
                    "sensor.lounge_humidity",
                    area="Lounge",
                    aliases='["Front Room", "Sitting Room"]',
                    state="64",
                    device_class="humidity",
                    unit="%",
                )
            ],
            now=NOW,
        )

        self.assertIn("Lounge humidity is 64 percent", result.content)
        self.assertIn("humid", result.content)

    def test_no_matching_sensor_returns_clean_error(self) -> None:
        with self.assertRaisesRegex(HomeAssistantSensorQueryError, "known humidity"):
            execute_sensor_query(
                parse_sensor_query("What's the humidity in the lounge?"),
                [
                    _sensor(
                        "sensor.lounge_temperature",
                        area="Lounge",
                        state="21",
                        device_class="temperature",
                    )
                ],
                now=NOW,
            )

    def test_multiple_matching_sensors_are_ambiguous(self) -> None:
        rows = [
            _sensor(
                "sensor.lounge_temperature_one",
                area="Lounge",
                state="21",
                device_class="temperature",
            ),
            _sensor(
                "sensor.lounge_temperature_two",
                area="Lounge",
                state="22",
                device_class="temperature",
            ),
        ]
        with self.assertRaisesRegex(HomeAssistantSensorQueryError, "more than one"):
            execute_sensor_query(
                parse_sensor_query("What's the temperature in the lounge?"),
                rows,
                now=NOW,
            )

    def test_duplicate_alias_rows_do_not_create_false_sensor_ambiguity(self) -> None:
        row = _sensor(
            "sensor.lounge_temperature",
            area="Lounge",
            state="21",
            device_class="temperature",
            unit="°C",
        )

        result = execute_sensor_query(
            parse_sensor_query("What's the temperature in the lounge?"),
            [row, {**row, "alias_name": "room temperature"}],
            now=NOW,
        )

        self.assertEqual(result.entity_ids, ("sensor.lounge_temperature",))

    def test_unavailable_sensor_is_reported(self) -> None:
        result = execute_sensor_query(
            parse_sensor_query("What's the humidity on the landing?"),
            [
                _sensor(
                    "sensor.landing_humidity",
                    area="Landing",
                    state="unavailable",
                    device_class="humidity",
                )
            ],
            now=NOW,
        )

        self.assertEqual(result.status, "unavailable")
        self.assertIn("sensor is unavailable", result.content)

    def test_stale_sensor_marks_reading_as_stale(self) -> None:
        result = execute_sensor_query(
            parse_sensor_query("What's the humidity on the landing?"),
            [
                _sensor(
                    "sensor.landing_humidity",
                    area="Landing",
                    state="55",
                    device_class="humidity",
                    unit="%",
                    updated=NOW - timedelta(hours=8),
                )
            ],
            now=NOW,
        )

        self.assertIn("8 hours ago", result.content)
        self.assertIn("may be stale", result.content)

    def test_threshold_interpretations_cover_required_ranges(self) -> None:
        self.assertEqual(interpret_humidity(35), "dry")
        self.assertEqual(interpret_humidity(50), "comfortable")
        self.assertEqual(interpret_humidity(65), "humid")
        self.assertIn("very humid", interpret_humidity(75))
        self.assertEqual(interpret_temperature(14), "cold")
        self.assertEqual(interpret_temperature(17), "cool")
        self.assertEqual(interpret_temperature(18.9), "slightly cool")
        self.assertEqual(interpret_temperature(21), "comfortable")
        self.assertEqual(interpret_temperature(24), "warm")
        self.assertEqual(interpret_temperature(28), "hot")

    def test_temperature_comparison_uses_both_area_sensors(self) -> None:
        result = execute_sensor_query(
            parse_sensor_query("Which is warmer, the lounge or the landing?"),
            [
                _sensor(
                    "sensor.lounge_temperature",
                    area="Lounge",
                    state="21.8",
                    device_class="temperature",
                    unit="°C",
                ),
                _sensor(
                    "sensor.landing_temperature",
                    area="Landing",
                    state="19.2",
                    device_class="temperature",
                    unit="°C",
                ),
            ],
            now=NOW,
        )

        self.assertIn("Lounge is warmer by 2.6°C", result.content)
        self.assertEqual(len(result.entity_ids), 2)

    def test_area_climate_summary_combines_temperature_and_humidity(self) -> None:
        result = execute_sensor_query(
            parse_sensor_query(
                "What's the temperature and humidity in the lounge?"
            ),
            [
                _sensor(
                    "sensor.lounge_temperature",
                    area="Lounge",
                    state="21.8",
                    device_class="temperature",
                    unit="°C",
                ),
                _sensor(
                    "sensor.lounge_humidity",
                    area="Lounge",
                    state="56",
                    device_class="humidity",
                    unit="%",
                ),
            ],
            now=NOW,
        )

        self.assertIn("Lounge is 21.8°C with humidity at 56 percent", result.content)
        self.assertIn("temperature is comfortable", result.content)
        self.assertIn("humidity is comfortable", result.content)

    def test_availability_and_freshness_queries(self) -> None:
        rows = [
            _sensor(
                "sensor.lounge_temperature",
                area="Lounge",
                state="unavailable",
                device_class="temperature",
            ),
            _sensor(
                "sensor.landing_humidity",
                area="Landing",
                state="52",
                device_class="humidity",
                updated=NOW - timedelta(minutes=30),
            ),
        ]

        availability = execute_sensor_query(
            parse_sensor_query("Are any sensors unavailable?"),
            rows,
            now=NOW,
        )
        freshness = execute_sensor_query(
            parse_sensor_query("When was the landing sensor last updated?"),
            rows,
            now=NOW,
        )

        self.assertIn("Lounge Temperature", availability.content)
        self.assertIn("30 minutes ago", freshness.content)


if __name__ == "__main__":
    unittest.main()
