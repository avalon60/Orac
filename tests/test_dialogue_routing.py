"""Tests for explicit and database-authorised dialogue route selection."""

# Author: Clive Bostock
# Date: 20-Jul-2026
# Description: Verifies explicit web precedence and terminal RAG usage decisions.

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.dialogue_routing import DialogueRoutingService
from orac_core.knowledge.scope import KnowledgeScope
from orac_core.knowledge.scope import KnowledgeScopeAuthorizer


class _Registry:
    def __init__(self, scopes: set[KnowledgeScope] | None = None, *, fail=False):
        self.scopes = scopes or {KnowledgeScope("PLUGIN", "drop_box")}
        self.fail = fail

    def load_active_scopes(self) -> frozenset[KnowledgeScope]:
        if self.fail:
            from orac_core.knowledge.scope import KnowledgeScopeRegistryError

            raise KnowledgeScopeRegistryError("offline")
        return frozenset(self.scopes)


class _Authorization:
    def __init__(self, result: str = "RAG_USAGE_GRANTED") -> None:
        self.result = result

    def authorization_result(self, username: str, scope: KnowledgeScope) -> str:
        return self.result


def _service(
    *,
    result: str = "RAG_USAGE_GRANTED",
    scopes: set[KnowledgeScope] | None = None,
    aliases: dict[str, KnowledgeScope] | None = None,
    registry_fail: bool = False,
    max_scopes: int = 3,
) -> DialogueRoutingService:
    """Build a route service with deterministic database and registry doubles."""
    authorizer = KnowledgeScopeAuthorizer(
        aliases=aliases or {"drop box": KnowledgeScope("PLUGIN", "drop_box")},
        registry=_Registry(scopes, fail=registry_fail),
        authorization_repository=_Authorization(result),
        max_scopes_per_request=max_scopes,
    )
    return DialogueRoutingService(scope_authorizer=authorizer)


class DialogueRoutingTests(unittest.TestCase):
    """Verify route-selection controls without executing route side effects."""

    def setUp(self) -> None:
        self.service = _service()

    def test_explicit_web_directive_is_selected_before_weather_semantics(self) -> None:
        decision = self.service.explicit_route(
            "Search the web for tomorrow's weather in Leeds."
        )
        self.assertIsNotNone(decision)
        self.assertEqual(decision.route_type, "internet")

    def test_database_grant_resolves_knowledge_scope(self) -> None:
        decision = self.service.knowledge_route(
            "How do I configure a Drop Box processing profile?",
            authenticated_username="clive",
        )
        self.assertEqual(decision.route_type, "knowledge")
        self.assertEqual(decision.reason_codes, ("RAG_USAGE_GRANTED",))

    def test_missing_privilege_is_terminally_denied(self) -> None:
        decision = _service(result="RAG_USAGE_NOT_GRANTED").knowledge_route(
            "What does the Drop Box documentation say?",
            authenticated_username="clive",
        )
        self.assertEqual(decision.route_type, "knowledge_denied")
        self.assertEqual(decision.reason_codes, ("RAG_USAGE_NOT_GRANTED",))

    def test_unknown_explicit_knowledge_base_cannot_fall_through(self) -> None:
        decision = self.service.explicit_knowledge_route(
            "Use the private archive knowledge base to answer this.",
            authenticated_username="clive",
        )
        self.assertEqual(decision.route_type, "clarification")
        self.assertEqual(decision.reason_codes, ("knowledge_scope_unknown",))

    def test_ambiguous_unnamed_knowledge_base_asks_for_scope(self) -> None:
        decision = self.service.explicit_knowledge_route(
            "Use the knowledge base to answer this.",
            authenticated_username="clive",
        )
        self.assertEqual(decision.route_type, "clarification")
        self.assertEqual(decision.reason_codes, ("knowledge_scope_required",))

    def test_excessive_multi_scope_request_requires_narrowing(self) -> None:
        scopes = tuple(
            KnowledgeScope("PROJECT", code)
            for code in ("ALPHA", "BETA", "GAMMA", "DELTA")
        )
        decision = _service(
            scopes=set(scopes),
            aliases={scope.scope_key.casefold(): scope for scope in scopes},
            max_scopes=3,
        ).knowledge_route(
            "What do Alpha, Beta, Gamma, and Delta documentation say?",
            authenticated_username="clive",
        )
        self.assertEqual(decision.route_type, "clarification")
        self.assertEqual(decision.reason_codes, ("knowledge_scope_limit_exceeded",))

    def test_inactive_scope_is_terminally_unavailable(self) -> None:
        decision = _service(
            scopes={KnowledgeScope("PLUGIN", "drop_box")},
            aliases={"orac": KnowledgeScope("PROJECT", "ORAC_CORE")},
        ).knowledge_route(
            "What does the Orac documentation say?",
            authenticated_username="clive",
        )
        self.assertEqual(decision.route_type, "knowledge_unavailable")
        self.assertEqual(decision.reason_codes, ("knowledge_scope_inactive",))

    def test_authorization_failure_is_terminally_unavailable(self) -> None:
        decision = _service(
            result="RAG_USAGE_AUTHORIZATION_UNAVAILABLE"
        ).knowledge_route(
            "What does the Drop Box documentation say?",
            authenticated_username="clive",
        )
        self.assertEqual(decision.route_type, "knowledge_unavailable")

    def test_registry_failure_is_terminally_unavailable(self) -> None:
        decision = _service(registry_fail=True).knowledge_route(
            "What does the Drop Box documentation say?",
            authenticated_username="clive",
        )
        self.assertEqual(decision.route_type, "knowledge_unavailable")
        self.assertEqual(decision.reason_codes, ("scope_registry_unavailable",))


if __name__ == "__main__":
    unittest.main()
