"""Tests for Home Assistant startup sync coordination."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Verifies Home Assistant sync ordering and repository calls.

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

from home_assistant.sync import HomeAssistantSyncCoordinator


class _FakeClient:
    def __init__(self, *, fail_entities: bool = False, fail_states: bool = False) -> None:
        self.fail_entities = fail_entities
        self.fail_states = fail_states

    def fetch_areas(self) -> list[dict]:
        return [{"area_id": "kitchen"}]

    def fetch_devices(self) -> list[dict]:
        return [{"id": "device-1"}]

    def fetch_entities(self) -> list[dict]:
        if self.fail_entities:
            raise RuntimeError("entity failure")
        return [{"entity_id": "light.kitchen"}]

    def fetch_states(self) -> list[dict]:
        if self.fail_states:
            raise RuntimeError("state failure")
        return [{"entity_id": "light.kitchen", "state": "on"}]


class _FakeRepository:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def begin_sync_run(self, sync_type: str) -> str:
        self.calls.append(("begin", sync_type))
        return f"{sync_type}-run"

    def complete_sync_run(
        self,
        sync_run_id: str,
        *,
        rows_processed: int,
        message: str | None = None,
    ) -> None:
        self.calls.append(("complete", sync_run_id, rows_processed, message))

    def fail_sync_run(self, sync_run_id: str, *, error_message: str) -> None:
        self.calls.append(("fail", sync_run_id, error_message))

    def merge_area(self, payload: dict) -> None:
        self.calls.append(("area", payload))

    def merge_device(self, payload: dict) -> None:
        self.calls.append(("device", payload))

    def merge_entity(self, payload: dict) -> None:
        self.calls.append(("entity", payload))

    def merge_state(self, payload: dict) -> None:
        self.calls.append(("state", payload))

    def commit(self) -> None:
        self.calls.append(("commit",))

    def rollback(self) -> None:
        self.calls.append(("rollback",))


class HomeAssistantSyncTests(unittest.TestCase):
    """Tests Home Assistant sync coordinator behaviour."""

    def test_successful_startup_runs_structural_then_state_sync(self) -> None:
        repository = _FakeRepository()
        coordinator = HomeAssistantSyncCoordinator(
            client=_FakeClient(),
            repository=repository,
        )

        structural, state = coordinator.run_initial_sync()

        self.assertEqual(structural.sync_type, "structural")
        self.assertEqual(structural.rows_processed, 3)
        self.assertEqual(state.sync_type, "state")
        self.assertEqual(state.rows_processed, 1)
        self.assertEqual(
            repository.calls,
            [
                ("begin", "structural"),
                ("area", {"area_id": "kitchen"}),
                ("device", {"id": "device-1"}),
                ("entity", {"entity_id": "light.kitchen"}),
                ("complete", "structural-run", 3, None),
                ("commit",),
                ("begin", "state"),
                ("state", {"entity_id": "light.kitchen", "state": "on"}),
                ("complete", "state-run", 1, None),
                ("commit",),
            ],
        )

    def test_structural_failure_after_begin_records_failed_run(self) -> None:
        repository = _FakeRepository()
        coordinator = HomeAssistantSyncCoordinator(
            client=_FakeClient(fail_entities=True),
            repository=repository,
        )

        with self.assertRaisesRegex(RuntimeError, "entity failure"):
            coordinator.run_structural_sync()

        self.assertIn(("begin", "structural"), repository.calls)
        self.assertIn(("fail", "structural-run", "entity failure"), repository.calls)
        self.assertEqual(repository.calls[-1], ("commit",))

    def test_state_failure_after_begin_records_failed_run(self) -> None:
        repository = _FakeRepository()
        coordinator = HomeAssistantSyncCoordinator(
            client=_FakeClient(fail_states=True),
            repository=repository,
        )

        with self.assertRaisesRegex(RuntimeError, "state failure"):
            coordinator.run_state_sync()

        self.assertIn(("begin", "state"), repository.calls)
        self.assertIn(("fail", "state-run", "state failure"), repository.calls)
        self.assertEqual(repository.calls[-1], ("commit",))

    def test_python_runtime_contains_no_raw_orac_ha_table_dml(self) -> None:
        runtime_files = [
            Path("plugins/home_assistant/client.py"),
            Path("plugins/home_assistant/service.py"),
            Path("plugins/home_assistant/sync.py"),
            Path("plugins/home_assistant/repository.py"),
        ]
        forbidden = (
            "insert into orac_ha.",
            "update orac_ha.",
            "delete from orac_ha.",
            "merge into orac_ha.",
            "truncate table orac_ha.",
        )

        for runtime_file in runtime_files:
            with self.subTest(path=str(runtime_file)):
                text = runtime_file.read_text(encoding="utf-8").lower()
                for token in forbidden:
                    self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
