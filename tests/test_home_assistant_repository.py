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
from home_assistant.control import ControlRequest


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
        repository.merge_area({"area_id": "kitchen", "name": "Kitchen"})
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
                ['{"area_id":"kitchen","name":"Kitchen"}'],
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


if __name__ == "__main__":
    unittest.main()
