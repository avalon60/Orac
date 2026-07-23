"""Tests for database-maintained RAG usage scope authorisation."""

# Author: Clive Bostock
# Date: 20-Jul-2026
# Description: Verifies database decisions, scope eligibility, bypass safety, and configuration migration.

from __future__ import annotations

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
    def __init__(
        self,
        *,
        aliases: str = '{"drop box": "PLUGIN:drop_box"}',
        allow_all: bool = False,
        obsolete: bool = False,
    ) -> None:
        self.values = {
            ("knowledge.dialogue", "scope_aliases_json"): aliases,
        }
        self.allow_all = allow_all
        self.obsolete = obsolete

    def config_value(self, section: str, key: str, default: str = "") -> str:
        return self.values.get((section, key), default)

    def int_config_value(self, section: str, key: str, default: int = 0) -> int:
        return default

    def bool_config_value(self, section: str, key: str, default: bool = False) -> bool:
        if (section, key) == ("knowledge.dialogue", "allow_all_scopes"):
            return self.allow_all
        return default

    def section_dict(self, section: str) -> dict[str, str]:
        if section == "knowledge.dialogue" and self.obsolete:
            return {"user_scope_allowlist_json": "{}"}
        return {}


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


class _Authorization:
    def __init__(self, result: str = "RAG_USAGE_GRANTED") -> None:
        self.result = result
        self.fail = False
        self.calls: list[tuple[str, KnowledgeScope]] = []

    def authorization_result(self, username: str, scope: KnowledgeScope) -> str:
        self.calls.append((username, scope))
        if self.fail:
            raise KnowledgeScopeRegistryError("offline")
        return self.result


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
    """Verify database privileges never widen canonical registry scope."""

    def _authorizer(
        self,
        registry: _Registry,
        authorization: _Authorization | None = None,
        *,
        allow_all: bool = False,
        clock=lambda: 0.0,
    ) -> KnowledgeScopeAuthorizer:
        return KnowledgeScopeAuthorizer(
            aliases={
                "orac": KnowledgeScope("PROJECT", "ORAC_CORE"),
                "drop box": KnowledgeScope("PLUGIN", "drop_box"),
            },
            registry=registry,
            authorization_repository=authorization or _Authorization(),
            allow_all_scopes=allow_all,
            cache_ttl_seconds=30,
            clock=clock,
        )

    def test_active_database_privilege_authorises_canonical_scope(self) -> None:
        registry = _Registry({KnowledgeScope("PLUGIN", "drop_box")})
        result = self._authorizer(registry).resolve_for_user("clive", ("drop box",))

        self.assertEqual(result.status, "authorised")
        self.assertEqual(result.reason_code, "RAG_USAGE_GRANTED")
        self.assertEqual(result.scopes[0].canonical_name, "PLUGIN:drop_box")

    def test_missing_expired_and_unknown_principal_fail_closed(self) -> None:
        registry = _Registry({KnowledgeScope("PLUGIN", "drop_box")})
        for code in (
            "RAG_USAGE_NOT_GRANTED",
            "RAG_USAGE_EXPIRED",
            "RAG_USAGE_PRINCIPAL_UNKNOWN",
            "RAG_USAGE_PRINCIPAL_INACTIVE",
        ):
            with self.subTest(code=code):
                result = self._authorizer(
                    registry, _Authorization(code)
                ).resolve_for_user("clive", ("drop box",))
                self.assertEqual(result.status, "denied")
                self.assertEqual(result.reason_code, code)

    def test_unknown_scope_is_clarification_without_database_call(self) -> None:
        authorization = _Authorization()
        result = self._authorizer(
            _Registry({KnowledgeScope("PLUGIN", "drop_box")}), authorization
        ).resolve_for_user("clive", ("missing",))

        self.assertEqual(result.status, "unknown")
        self.assertEqual(authorization.calls, [])

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

    def test_database_failure_never_activates_allow_all(self) -> None:
        authorization = _Authorization("RAG_USAGE_NOT_GRANTED")
        authorization.fail = True
        result = self._authorizer(
            _Registry({KnowledgeScope("PLUGIN", "drop_box")}),
            authorization,
            allow_all=True,
        ).resolve_for_user("clive", ("drop box",))

        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, "RAG_USAGE_AUTHORIZATION_UNAVAILABLE")

    def test_allow_all_skips_only_missing_privilege(self) -> None:
        registry = _Registry({KnowledgeScope("PLUGIN", "drop_box")})
        result = self._authorizer(
            registry,
            _Authorization("RAG_USAGE_NOT_GRANTED"),
            allow_all=True,
        ).resolve_for_user("clive", ("drop box",))

        self.assertEqual(result.status, "authorised")
        self.assertEqual(result.reason_code, "rag_usage_allow_all_scopes")

    def test_allow_all_never_bypasses_principal_or_scope_activity(self) -> None:
        denied = self._authorizer(
            _Registry({KnowledgeScope("PLUGIN", "drop_box")}),
            _Authorization("RAG_USAGE_PRINCIPAL_UNKNOWN"),
            allow_all=True,
        ).resolve_for_user("unknown", ("drop box",))
        inactive = self._authorizer(
            _Registry(set()),
            _Authorization("RAG_USAGE_NOT_GRANTED"),
            allow_all=True,
        ).resolve_for_user("clive", ("drop box",))

        self.assertEqual(denied.status, "denied")
        self.assertEqual(inactive.status, "inactive")

    def test_obsolete_allowlist_is_rejected(self) -> None:
        with self.assertRaisesRegex(KnowledgeScopeConfigurationError, "obsolete"):
            KnowledgeScopeAuthorizer.validate_config(_Config(obsolete=True))

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

    def test_shipped_configuration_is_fail_closed(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = ConfigManager(PROJECT_ROOT / "resources/config/orac.ini")

        self.assertFalse(config.bool_config_value("knowledge.dialogue", "enabled"))
        self.assertFalse(
            config.bool_config_value("knowledge.dialogue", "allow_all_scopes")
        )
        self.assertNotIn(
            "user_scope_allowlist_json",
            config.section_dict("knowledge.dialogue"),
        )


if __name__ == "__main__":
    unittest.main()
