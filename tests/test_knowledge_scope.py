"""Tests for canonical per-user knowledge scope authorisation."""

# Author: Clive Bostock
# Date: 18-Jul-2026
# Description: Verifies config parsing, live registry validation, cache expiry, and fail-closed behavior.

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from lib.config_mgr import ConfigManager
from model.plugin_registry import PluginRegistryStore
from orac_core.knowledge.scope import KnowledgeScope
from orac_core.knowledge.scope import KnowledgeScopeAuthorizer
from orac_core.knowledge.scope import KnowledgeScopeConfigurationError
from orac_core.knowledge.scope import KnowledgeScopeRegistryRepository
from orac_core.knowledge.scope import KnowledgeScopeRegistryError


class _Config:
    def __init__(self, *, allowlist: str, aliases: str) -> None:
        self.values = {
            ("knowledge.dialogue", "user_scope_allowlist_json"): allowlist,
            ("knowledge.dialogue", "scope_aliases_json"): aliases,
        }

    def config_value(self, section: str, key: str, default: str = "") -> str:
        return self.values.get((section, key), default)

    def int_config_value(self, section: str, key: str, default: int = 0) -> int:
        return default


class _Registry:
    def __init__(self, scopes: set[KnowledgeScope]) -> None:
        self.scopes = scopes
        self.fail = False
        self.calls = 0

    def load_active_scopes(self) -> frozenset[KnowledgeScope]:
        self.calls += 1
        if self.fail:
            raise KnowledgeScopeRegistryError("offline")
        return frozenset(self.scopes)


class _PolicyCursor:
    """Return one supplied plugin row for both approved registry adapters."""

    def __init__(self, row: dict[str, str]) -> None:
        self.row = row
        self.description: list[tuple[str]] = []
        self.rows: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None

    def execute(self, sql: str, binds=None) -> None:
        if "project_registry_v" in sql:
            self.description = [("PROJECT_CODE",), ("ACTIVE_YN",)]
            self.rows = []
            return
        self.description = [(key.upper(),) for key in self.row]
        self.rows = [tuple(self.row[key] for key in self.row)]

    def fetchall(self) -> list[tuple]:
        return list(self.rows)


class _PolicySession:
    def __init__(self, row: dict[str, str]) -> None:
        self.cursor_instance = _PolicyCursor(row)

    def cursor(self) -> _PolicyCursor:
        return self.cursor_instance

    def close(self) -> None:
        return None


def _eligible_plugin_row() -> dict[str, str]:
    """Return a minimal row that passes every runtime eligibility gate."""
    return {
        "plugin_id": "drop_box",
        "enabled": "Y",
        "install_status": "success",
        "configuration_status": "not_required",
        "dependency_status": "not_required",
        "database_status": "optional_missing",
        "readiness_status": "success",
    }


class KnowledgeScopeAuthorizerTests(unittest.TestCase):
    """Verify configured grants never widen canonical registry scope."""

    def _authorizer(self, registry: _Registry, clock=lambda: 0.0):
        return KnowledgeScopeAuthorizer(
            user_allowlist={
                "clive": (
                    KnowledgeScope("PROJECT", "ORAC_CORE"),
                    KnowledgeScope("PLUGIN", "drop_box"),
                )
            },
            aliases={
                "orac": KnowledgeScope("PROJECT", "ORAC_CORE"),
                "drop box": KnowledgeScope("PLUGIN", "drop_box"),
            },
            registry=registry,
            cache_ttl_seconds=30,
            clock=clock,
        )

    def test_authorised_scope_is_canonical_and_active(self) -> None:
        registry = _Registry({KnowledgeScope("PLUGIN", "drop_box")})
        result = self._authorizer(registry).resolve_for_user("clive", ("drop box",))

        self.assertEqual(result.status, "authorised")
        self.assertEqual(result.scopes[0].canonical_name, "PLUGIN:drop_box")

    def test_unknown_user_and_scope_fail_closed(self) -> None:
        registry = _Registry({KnowledgeScope("PLUGIN", "drop_box")})
        authorizer = self._authorizer(registry)

        self.assertEqual(
            authorizer.resolve_for_user("unknown", ("drop box",)).reason_code,
            "user_scope_allowlist_missing",
        )
        self.assertEqual(
            authorizer.resolve_for_user("clive", ("missing",)).reason_code,
            "knowledge_scope_unknown",
        )

    def test_expired_registry_failure_does_not_serve_stale_scope(self) -> None:
        now = [0.0]
        registry = _Registry({KnowledgeScope("PLUGIN", "drop_box")})
        authorizer = self._authorizer(registry, clock=lambda: now[0])
        self.assertEqual(
            authorizer.resolve_for_user("clive", ("drop box",)).status,
            "authorised",
        )

        now[0] = 31.0
        registry.fail = True
        result = authorizer.resolve_for_user("clive", ("drop box",))

        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, "scope_registry_unavailable")

    def test_duplicate_json_keys_are_rejected(self) -> None:
        config = _Config(
            allowlist='{"clive": ["PLUGIN:drop_box"], "clive": []}',
            aliases='{"drop box": "PLUGIN:drop_box"}',
        )

        with self.assertRaisesRegex(KnowledgeScopeConfigurationError, "duplicate"):
            KnowledgeScopeAuthorizer.from_config(config, registry=_Registry(set()))

    def test_duplicate_scope_values_are_deduplicated(self) -> None:
        config = _Config(
            allowlist=('{"clive": ["PLUGIN:drop_box", "PLUGIN:drop_box"]}'),
            aliases='{"drop box": "PLUGIN:drop_box"}',
        )
        registry = _Registry({KnowledgeScope("PLUGIN", "drop_box")})
        authorizer = KnowledgeScopeAuthorizer.from_config(config, registry=registry)

        result = authorizer.resolve_for_user("clive", ("drop box",))

        self.assertEqual(len(result.scopes), 1)

    def test_runtime_and_knowledge_adapters_share_every_eligibility_gate(self) -> None:
        cases = {
            "eligible": (None, None, True),
            "enabled": ("enabled", "N", False),
            "installation": ("install_status", "failed", False),
            "configuration": ("configuration_status", "failed", False),
            "dependency": ("dependency_status", "failed", False),
            "database": ("database_status", "failed", False),
            "readiness": ("readiness_status", "failed", False),
        }
        for label, (key, value, expected) in cases.items():
            with self.subTest(gate=label):
                row = _eligible_plugin_row()
                if key is not None:
                    row[key] = value
                runtime_rows = PluginRegistryStore(
                    session_factory=lambda row=row: _PolicySession(row)
                ).list_enabled()
                knowledge_scopes = KnowledgeScopeRegistryRepository(
                    session_factory=lambda row=row: _PolicySession(row)
                ).load_active_scopes()

                self.assertEqual(bool(runtime_rows), expected)
                self.assertEqual(
                    KnowledgeScope("PLUGIN", "drop_box") in knowledge_scopes,
                    expected,
                )

    def test_shipped_configuration_is_disabled_with_empty_allowlist(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = ConfigManager(PROJECT_ROOT / "resources/config/orac.ini")

        self.assertFalse(config.bool_config_value("knowledge.dialogue", "enabled"))
        self.assertEqual(
            json.loads(
                config.config_value("knowledge.dialogue", "user_scope_allowlist_json")
            ),
            {},
        )

    def test_enabled_feature_with_empty_allowlist_denies_user(self) -> None:
        with patch.dict(
            os.environ,
            {"ORAC__KNOWLEDGE.DIALOGUE__ENABLED": "true"},
            clear=True,
        ):
            config = ConfigManager(PROJECT_ROOT / "resources/config/orac.ini")
        authorizer = KnowledgeScopeAuthorizer.from_config(
            config,
            registry=_Registry({KnowledgeScope("PLUGIN", "drop_box")}),
        )

        self.assertTrue(config.bool_config_value("knowledge.dialogue", "enabled"))
        self.assertEqual(
            authorizer.resolve_for_user("clive", ("drop box",)).reason_code,
            "user_scope_allowlist_missing",
        )

    def test_environment_overrides_enable_and_grant_exact_scope(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ORAC__KNOWLEDGE.DIALOGUE__ENABLED": "true",
                "ORAC__KNOWLEDGE.DIALOGUE__USER_SCOPE_ALLOWLIST_JSON": (
                    '{"clive":["PLUGIN:drop_box"]}'
                ),
            },
            clear=True,
        ):
            config = ConfigManager(PROJECT_ROOT / "resources/config/orac.ini")
        authorizer = KnowledgeScopeAuthorizer.from_config(
            config,
            registry=_Registry({KnowledgeScope("PLUGIN", "drop_box")}),
        )

        self.assertTrue(config.bool_config_value("knowledge.dialogue", "enabled"))
        self.assertEqual(
            authorizer.resolve_for_user("clive", ("drop box",)).status,
            "authorised",
        )


if __name__ == "__main__":
    unittest.main()
