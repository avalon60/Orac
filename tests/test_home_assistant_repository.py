"""Tests for the Home Assistant plugin database repository."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Verifies Home Assistant sync persistence uses managed package APIs.

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
for path in (SRC_ROOT, PLUGINS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from home_assistant.repository import HomeAssistantRepository
from home_assistant.control import AreaListRequest
from home_assistant.control import ControlRequest
from home_assistant.sensor_query import SensorQueryRequest
from home_assistant.status import redact_sensitive_text


class _FakePluginDatabaseSession:
    def __init__(self) -> None:
        self.connected_username = "ORAC_PLUGIN"
        self.procedure_calls: list[tuple[str, list]] = []
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.fetch_rows: list[dict] = []
        self.fetch_queries: list[str] = []

    def call_procedure(
        self,
        procedure_name: str,
        parameters: list | None = None,
        *,
        auto_commit: bool = False,
    ) -> list:
        self.procedure_calls.append((procedure_name, list(parameters or [])))
        return list(parameters or [])

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True

    def fetch_dicts(self, sql_query: str, bind_vars=None) -> list[dict]:
        self.fetch_queries.append(sql_query)
        return self.fetch_rows


class _FakeContext:
    def __init__(self, session: _FakePluginDatabaseSession) -> None:
        self.session = session
        self.session_calls = 0

    def plugin_db_session(self) -> _FakePluginDatabaseSession:
        self.session_calls += 1
        return self.session


class HomeAssistantRepositoryTests(unittest.TestCase):
    """Tests the Home Assistant repository package-call boundary."""

    def test_repository_uses_managed_session_package_calls(self) -> None:
        session = _FakePluginDatabaseSession()
        context = _FakeContext(session)
        repository = HomeAssistantRepository(
            context,
            run_id_factory=lambda: "sync-run-1",
        )

        sync_run_id = repository.begin_sync_run("structural")
        repository.merge_area(
            {"area_id": "kitchen", "name": "Kitchen", "aliases": ["Galley"]}
        )
        repository.merge_device({"id": "device-1", "name": "Lamp"})
        repository.merge_entity({"entity_id": "light.kitchen"})
        repository.merge_state({"entity_id": "light.kitchen", "state": "on"})
        repository.complete_sync_run(sync_run_id, rows_processed=4)
        repository.commit()

        self.assertEqual(sync_run_id, "sync-run-1")
        self.assertEqual(context.session_calls, 1)
        procedure_names = [name for name, _parameters in session.procedure_calls]
        self.assertEqual(
            procedure_names,
            [
                "orac_ha.ha_sync_api.begin_sync_run",
                "orac_ha.ha_sync_api.merge_area",
                "orac_ha.ha_sync_api.merge_device",
                "orac_ha.ha_sync_api.merge_entity",
                "orac_ha.ha_sync_api.merge_state",
                "orac_ha.ha_sync_api.complete_sync_run",
            ],
        )
        self.assertEqual(
            session.procedure_calls[0],
            ("orac_ha.ha_sync_api.begin_sync_run", ["sync-run-1", "structural"]),
        )
        self.assertEqual(
            session.procedure_calls[-1],
            ("orac_ha.ha_sync_api.complete_sync_run", ["sync-run-1", 4, None]),
        )
        self.assertEqual(
            session.procedure_calls[1],
            (
                "orac_ha.ha_sync_api.merge_area",
                ['{"aliases":["Galley"],"area_id":"kitchen","name":"Kitchen"}'],
            ),
        )
        self.assertEqual(
            session.procedure_calls[2],
            (
                "orac_ha.ha_sync_api.merge_device",
                ['{"id":"device-1","name":"Lamp"}'],
            ),
        )
        self.assertEqual(
            session.procedure_calls[3],
            (
                "orac_ha.ha_sync_api.merge_entity",
                ['{"entity_id":"light.kitchen"}'],
            ),
        )
        self.assertEqual(
            session.procedure_calls[4],
            (
                "orac_ha.ha_sync_api.merge_state",
                ['{"entity_id":"light.kitchen","state":"on"}'],
            ),
        )
        self.assertTrue(session.committed)

    def test_fail_sync_run_redacts_sensitive_error_values(self) -> None:
        session = _FakePluginDatabaseSession()
        repository = HomeAssistantRepository(_FakeContext(session))

        repository.fail_sync_run(
            "sync-run-1",
            error_message=(
                "Authorization: Bearer abc.def.ghi failed for "
                "http://user:pass@ha.local/api?access_token=secret-token"
            ),
        )

        _name, parameters = session.procedure_calls[-1]
        self.assertEqual(parameters[0], "sync-run-1")
        self.assertNotIn("abc.def.ghi", parameters[1])
        self.assertNotIn("user:pass", parameters[1])
        self.assertNotIn("secret-token", parameters[1])
        self.assertIn("[redacted]", parameters[1])

    def test_status_summary_reads_expected_fields_from_summary_view(self) -> None:
        session = _FakePluginDatabaseSession()
        session.fetch_rows = [
            {
                "PLUGIN_ID": "home_assistant",
                "SERVICE_RUNNING": None,
                "API_REACHABLE": None,
                "LAST_STARTUP_SYNC_AT": "2026-06-20T10:00:00Z",
                "LAST_STARTUP_SYNC_STATUS": "complete",
                "LAST_STATE_SYNC_AT": "2026-06-20T10:01:00Z",
                "LAST_STATE_SYNC_STATUS": "failed",
                "LAST_AREAS_PROCESSED": 2,
                "LAST_DEVICES_PROCESSED": 4,
                "LAST_ENTITIES_PROCESSED": 8,
                "LAST_STATES_PROCESSED": 7,
                "LAST_ERROR_MESSAGE_REDACTED": "password=[redacted]",
                "UPDATED_AT": "2026-06-20T10:02:00Z",
            }
        ]
        repository = HomeAssistantRepository(_FakeContext(session))

        summary = repository.status_summary(
            service_running=True,
            api_reachable=False,
        ).as_dict()

        self.assertEqual(summary["plugin_id"], "home_assistant")
        self.assertTrue(summary["service_running"])
        self.assertFalse(summary["api_reachable"])
        self.assertEqual(summary["last_startup_sync_status"], "complete")
        self.assertEqual(summary["last_state_sync_status"], "failed")
        self.assertEqual(summary["last_areas_processed"], 2)
        self.assertEqual(summary["last_devices_processed"], 4)
        self.assertEqual(summary["last_entities_processed"], 8)
        self.assertEqual(summary["last_states_processed"], 7)
        self.assertEqual(summary["last_error_message_redacted"], "password=[redacted]")
        self.assertIn("ha_status_summary_v", session.fetch_queries[-1])

    def test_redaction_removes_common_secret_shapes(self) -> None:
        redacted = redact_sensitive_text(
            'Bearer token-123 access_token="ha-secret" '
            'password=letmein {"api_key":"abc"} http://user:pass@example.test/path'
        )

        self.assertNotIn("token-123", redacted)
        self.assertNotIn("ha-secret", redacted)
        self.assertNotIn("letmein", redacted)
        self.assertNotIn("abc", redacted)
        self.assertNotIn("user:pass", redacted)
        self.assertGreaterEqual(redacted.count("[redacted]"), 5)

    def test_status_summary_database_surface_is_narrow_and_redacted(self) -> None:
        schema_root = PROJECT_ROOT / "plugins" / "home_assistant" / "db" / "schema"
        view_sql = (
            schema_root / "view" / "ha_status_summary_v.sql"
        ).read_text(encoding="utf-8").lower()
        grants = " ".join(
            path.read_text(encoding="utf-8").lower()
            for path in (schema_root / "grant").glob("ha_status_summary_v_to_*.sql")
        )

        self.assertIn("ha_status_summary_v", view_sql)
        self.assertIn("last_error_message_redacted", view_sql)
        self.assertIn("regexp_replace", view_sql)
        self.assertIn("grant select on orac_ha.ha_status_summary_v to orac_plugin", grants)
        self.assertIn("grant select on orac_ha.ha_status_summary_v to orac_apx_pub", grants)
        self.assertNotIn("grant all", grants)

    def test_repository_failure_logging_uses_package_api_and_sanitises_message(self) -> None:
        session = _FakePluginDatabaseSession()
        context = _FakeContext(session)
        repository = HomeAssistantRepository(
            context,
            run_id_factory=lambda: "sync-run-2",
        )

        repository.fail_sync_run("sync-run-2", error_message="first line\nsecond line")

        self.assertEqual(
            session.procedure_calls,
            [
                (
                    "orac_ha.ha_sync_api.fail_sync_run",
                    ["sync-run-2", "first line second line"],
                )
            ],
        )

    def test_repository_rejects_non_orac_plugin_identity(self) -> None:
        session = _FakePluginDatabaseSession()
        session.connected_username = "ORAC_HA"
        context = _FakeContext(session)

        with self.assertRaisesRegex(RuntimeError, "ORAC_PLUGIN"):
            HomeAssistantRepository(context)

    def test_repository_does_not_require_raw_dml_methods(self) -> None:
        session = _FakePluginDatabaseSession()
        context = _FakeContext(session)
        repository = HomeAssistantRepository(
            context,
            run_id_factory=lambda: "sync-run-3",
        )

        repository.begin_sync_run("state")
        repository.merge_state({"entity_id": "light.kitchen", "state": "on"})
        repository.complete_sync_run("sync-run-3", rows_processed=1)

        self.assertFalse(hasattr(session, "execute"))
        self.assertFalse(hasattr(session, "cursor"))

    def test_control_resolution_reads_only_the_granted_view(self) -> None:
        session = _FakePluginDatabaseSession()
        session.fetch_rows = [
            {
                "ENTITY_ID": "light.office",
                "DOMAIN": "light",
                "OBJECT_ID": "office",
                "FRIENDLY_NAME": "Office Light",
            }
        ]
        repository = HomeAssistantRepository(_FakeContext(session))

        resolved = repository.resolve_control(
            ControlRequest("turn_on", "office light", "light")
        )

        self.assertEqual(resolved.entity_ids, ("light.office",))
        self.assertIn("orac_ha.ha_control_resolution_v", session.fetch_queries[0])

    def test_area_listing_reads_only_the_granted_view(self) -> None:
        session = _FakePluginDatabaseSession()
        session.fetch_rows = [
            {
                "ENTITY_ID": "switch.desk_lamp",
                "DOMAIN": "switch",
                "OBJECT_ID": "desk_lamp",
                "DEVICE_NAME": "Desk Lamp",
                "AREA_NAME": "Office",
                "AREA_ALIASES": '["Study"]',
            }
        ]
        repository = HomeAssistantRepository(_FakeContext(session))

        result = repository.list_area(AreaListRequest("study"))

        self.assertEqual(result.area_name, "office")
        self.assertEqual(result.devices[0].name, "desk lamp")
        self.assertIn("orac_ha.ha_control_resolution_v", session.fetch_queries[0])

    def test_sensor_query_reads_only_the_granted_view(self) -> None:
        session = _FakePluginDatabaseSession()
        session.fetch_rows = [
            {
                "ENTITY_ID": "sensor.lounge_temperature",
                "DOMAIN": "sensor",
                "OBJECT_ID": "lounge_temperature",
                "FRIENDLY_NAME": "Lounge Temperature",
                "AREA_NAME": "Lounge",
                "CURRENT_STATE": "21.4",
                "DEVICE_CLASS": "temperature",
                "UNIT_OF_MEASUREMENT": "°C",
                "LAST_UPDATED": "2026-06-12T11:48:00+00:00",
            }
        ]
        repository = HomeAssistantRepository(_FakeContext(session))

        result = repository.query_sensors(
            SensorQueryRequest(
                intent="area_temperature",
                areas=("lounge",),
                sensor_role="temperature",
            ),
            stale_after_hours=6,
            live_states=[
                {
                    "entity_id": "sensor.lounge_temperature",
                    "state": "19.8",
                    "attributes": {
                        "device_class": "temperature",
                        "unit_of_measurement": "°C",
                    },
                    "last_changed": "2026-06-12T12:00:00+00:00",
                    "last_updated": "2026-06-12T12:00:00+00:00",
                }
            ],
        )

        self.assertIn("Lounge temperature is 19.8°C", result.content)
        self.assertIn("device_class", session.fetch_queries[0])
        self.assertIn("last_updated", session.fetch_queries[0])
        self.assertIn("orac_ha.ha_control_resolution_v", session.fetch_queries[0])
        self.assertEqual(session.procedure_calls, [])

    def test_sensor_query_does_not_use_shadow_reading_missing_from_live_states(self) -> None:
        session = _FakePluginDatabaseSession()
        session.fetch_rows = [
            {
                "ENTITY_ID": "sensor.lounge_temperature",
                "DOMAIN": "sensor",
                "OBJECT_ID": "lounge_temperature",
                "AREA_NAME": "Lounge",
                "CURRENT_STATE": "21.4",
                "DEVICE_CLASS": "temperature",
                "UNIT_OF_MEASUREMENT": "°C",
            }
        ]
        repository = HomeAssistantRepository(_FakeContext(session))

        result = repository.query_sensors(
            SensorQueryRequest(
                intent="area_temperature",
                areas=("lounge",),
                sensor_role="temperature",
            ),
            stale_after_hours=6,
            live_states=[],
        )

        self.assertIn("sensor is unavailable", result.content)
        self.assertNotIn("21.4", result.content)
        self.assertEqual(session.procedure_calls, [])

    def test_cached_sensor_fallback_is_explicitly_labelled(self) -> None:
        session = _FakePluginDatabaseSession()
        session.fetch_rows = [
            {
                "ENTITY_ID": "sensor.lounge_temperature",
                "DOMAIN": "sensor",
                "OBJECT_ID": "lounge_temperature",
                "AREA_NAME": "Lounge",
                "CURRENT_STATE": "21.4",
                "DEVICE_CLASS": "temperature",
                "UNIT_OF_MEASUREMENT": "°C",
                "LAST_UPDATED": "2026-06-12T11:48:00+00:00",
            }
        ]
        repository = HomeAssistantRepository(_FakeContext(session))

        result = repository.query_cached_sensors(
            SensorQueryRequest(
                intent="area_temperature",
                areas=("lounge",),
                sensor_role="temperature",
            ),
            stale_after_hours=6,
        )

        self.assertEqual(result.status, "cached")
        self.assertIn("cannot get a live reading", result.content)
        self.assertIn("Cached Home Assistant data", result.content)
        self.assertIn("21.4°C", result.content)


if __name__ == "__main__":
    unittest.main()
