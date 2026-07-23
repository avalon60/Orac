"""Tests for explicit and scoped normal-dialogue route selection."""

# Author: Clive Bostock
# Date: 18-Jul-2026
# Description: Verifies explicit web directives and canonical local-knowledge routes.

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
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def load_active_scopes(self) -> frozenset[KnowledgeScope]:
        if self.fail:
            from orac_core.knowledge.scope import KnowledgeScopeRegistryError

            raise KnowledgeScopeRegistryError("offline")
        return frozenset({KnowledgeScope("PLUGIN", "drop_box")})


class DialogueRoutingTests(unittest.TestCase):
    """Verify route-selection controls without executing route side effects."""

    def setUp(self) -> None:
        authorizer = KnowledgeScopeAuthorizer(
            user_allowlist={"clive": (KnowledgeScope("PLUGIN", "drop_box"),)},
            aliases={"drop box": KnowledgeScope("PLUGIN", "drop_box")},
            registry=_Registry(),
        )
        self.service = DialogueRoutingService(scope_authorizer=authorizer)

    def test_explicit_web_directive_is_selected_before_weather_semantics(self) -> None:
        decision = self.service.explicit_route(
            "Search the web for tomorrow's weather in Leeds."
        )

        self.assertIsNotNone(decision)
        self.assertEqual(decision.route_type, "internet")
        self.assertEqual(
            decision.external_search_request.query,
            "tomorrow's weather in Leeds",
        )

    def test_drop_box_question_resolves_authorised_plugin_scope(self) -> None:
        decision = self.service.knowledge_route(
            "How do I configure a Drop Box processing profile?",
            authenticated_username="clive",
        )

        self.assertIsNotNone(decision)
        self.assertEqual(decision.route_type, "knowledge")
        self.assertEqual(
            decision.knowledge_scopes[0].canonical_name,
            "PLUGIN:drop_box",
        )

    def test_unlisted_user_cannot_retrieve_configured_scope(self) -> None:
        decision = self.service.knowledge_route(
            "What does the Drop Box documentation say?",
            authenticated_username="unknown",
        )

        self.assertEqual(decision.route_type, "knowledge_denied")
        self.assertEqual(decision.fallback_reason, "user_scope_allowlist_missing")
        self.assertEqual(
            decision.user_visible_message,
            "I can’t use that knowledge source for this user.",
        )

    def test_listed_user_without_requested_scope_is_denied(self) -> None:
        service = DialogueRoutingService(
            scope_authorizer=KnowledgeScopeAuthorizer(
                user_allowlist={"clive": (KnowledgeScope("PROJECT", "ORAC_CORE"),)},
                aliases={"drop box": KnowledgeScope("PLUGIN", "drop_box")},
                registry=_Registry(),
            )
        )

        decision = service.explicit_knowledge_route(
            "Use the Drop Box knowledge base to explain processing profiles.",
            authenticated_username="clive",
        )

        self.assertEqual(decision.route_type, "knowledge_denied")
        self.assertEqual(
            decision.reason_codes,
            ("knowledge_scope_not_authorised",),
        )
        self.assertEqual(
            decision.user_visible_message,
            "I can’t use that knowledge source for this user.",
        )

    def test_unknown_explicit_knowledge_base_cannot_fall_through(self) -> None:
        decision = self.service.explicit_knowledge_route(
            "Use the private archive knowledge base to answer this.",
            authenticated_username="clive",
        )

        self.assertEqual(decision.route_type, "clarification")
        self.assertEqual(decision.reason_codes, ("knowledge_scope_unknown",))
        self.assertIn("authorised project or plugin", decision.user_visible_message)

    def test_ambiguous_unnamed_knowledge_base_asks_for_scope(self) -> None:
        decision = self.service.explicit_knowledge_route(
            "Use the knowledge base to answer this.",
            authenticated_username="clive",
        )

        self.assertEqual(decision.route_type, "clarification")
        self.assertEqual(decision.reason_codes, ("knowledge_scope_required",))

    def test_excessive_multi_scope_request_requires_narrowing(self) -> None:
        scopes = tuple(
            KnowledgeScope("PROJECT", project_code)
            for project_code in ("ALPHA", "BETA", "GAMMA", "DELTA")
        )
        service = DialogueRoutingService(
            scope_authorizer=KnowledgeScopeAuthorizer(
                user_allowlist={"clive": scopes},
                aliases={
                    scope.scope_key.casefold(): scope
                    for scope in scopes
                },
                registry=_Registry(),
                max_scopes_per_request=3,
            )
        )

        decision = service.knowledge_route(
            "What do Alpha, Beta, Gamma, and Delta documentation say?",
            authenticated_username="clive",
        )

        self.assertEqual(decision.route_type, "clarification")
        self.assertEqual(
            decision.reason_codes,
            ("knowledge_scope_limit_exceeded",),
        )
        self.assertIn("at most 3", decision.user_visible_message)

    def test_inactive_scope_is_terminally_unavailable(self) -> None:
        service = DialogueRoutingService(
            scope_authorizer=KnowledgeScopeAuthorizer(
                user_allowlist={"clive": (KnowledgeScope("PROJECT", "ORAC_CORE"),)},
                aliases={"orac": KnowledgeScope("PROJECT", "ORAC_CORE")},
                registry=_Registry(),
            )
        )

        decision = service.knowledge_route(
            "What does the Orac documentation say?",
            authenticated_username="clive",
        )

        self.assertEqual(decision.route_type, "knowledge_unavailable")
        self.assertEqual(decision.reason_codes, ("knowledge_scope_inactive",))
        self.assertEqual(
            decision.user_visible_message,
            "That knowledge source is unavailable right now.",
        )

    def test_registry_failure_is_terminally_unavailable(self) -> None:
        service = DialogueRoutingService(
            scope_authorizer=KnowledgeScopeAuthorizer(
                user_allowlist={"clive": (KnowledgeScope("PLUGIN", "drop_box"),)},
                aliases={"drop box": KnowledgeScope("PLUGIN", "drop_box")},
                registry=_Registry(fail=True),
            )
        )

        decision = service.knowledge_route(
            "What does the Drop Box documentation say?",
            authenticated_username="clive",
        )

        self.assertEqual(decision.route_type, "knowledge_unavailable")
        self.assertEqual(decision.reason_codes, ("scope_registry_unavailable",))


if __name__ == "__main__":
    unittest.main()
