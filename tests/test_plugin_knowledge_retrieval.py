"""Tests for host-owned plugin self-scope knowledge retrieval."""
# Author: Clive Bostock
# Date: 2026-08-26
# Description: Verifies immutable authority binding, entitlements, bounds, and DTOs.

from __future__ import annotations

from dataclasses import replace
import inspect
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_knowledge_retrieval import (  # noqa: E402
    PLUGIN_KNOWLEDGE_MAX_CHUNK_CHARS,
    PluginKnowledgeRetrievalResult,
    plugin_knowledge_bridge,
)
from model.plugin_routing.discovery import PluginDiscovery  # noqa: E402
from model.plugin_router import _has_self_scope_retrieval_entitlement  # noqa: E402
from model.plugin_runtime import PluginRuntimeContext  # noqa: E402
from orac_core.knowledge import KnowledgeRetrievalOutcome  # noqa: E402
from orac_core.knowledge import KnowledgeScope  # noqa: E402
from orac_core.knowledge import KnowledgeSearchResult  # noqa: E402

ENTITLEMENT = "knowledge.self_scope_retrieval"
RETRIEVAL_ID = "123e4567-e89b-42d3-a456-426614174000"


class _Logger:
    """Capture internal bridge errors."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def log_error(self, message: str) -> None:
        self.errors.append(message)


class _Service:
    """Return an injectable Core retrieval response."""

    def __init__(self, outcome: object) -> None:
        self.outcome = outcome
        self.calls: list[dict] = []

    def retrieve_for_plugin(self, query: str, **kwargs):
        self.calls.append({"query": query, **kwargs})
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def _manifest(*, declared: bool = True, effective: bool = True):
    manifests, errors = PluginDiscovery(Path("plugins")).discover()
    assert not errors
    source = next(item for item in manifests if item.plugin_id == "weather")
    declared_entitlements = (
        (*source.entitlements, ENTITLEMENT) if declared else source.entitlements
    )
    policy_entitlements = (
        (*source.execution_policy.entitlements, ENTITLEMENT)
        if effective
        else source.execution_policy.entitlements
    )
    return replace(
        source,
        entitlements=declared_entitlements,
        execution_policy=replace(
            source.execution_policy,
            entitlements=policy_entitlements,
        ),
    )


def _evidence(*, plugin_id: str = "weather", text: str = "weather evidence"):
    return KnowledgeSearchResult(
        ingestion_request_id=1,
        document_id=2,
        document_version_id=3,
        source_object_id=4,
        source_reference="opaque-reference",
        parent_source_reference=None,
        chunk_id=5,
        chunk_no=1,
        lexical_score=0.75,
        semantic_score=0.5,
        target_scope_type="PLUGIN",
        target_scope_key=plugin_id,
        embedding_model_identifier="hash-embedding-v1",
        embedding_dimensions=2,
        chunk_text=text,
        document_title="Weather guide",
    )


def _outcome(
    *,
    plugin_id: str = "weather",
    status: str = "grounded",
    results: tuple[KnowledgeSearchResult, ...] | None = None,
    text: str = "weather evidence",
):
    return KnowledgeRetrievalOutcome(
        status=status,
        reason_codes=(
            "local_evidence_selected" if status == "grounded" else "denied",
        ),
        scope=KnowledgeScope("PLUGIN", plugin_id),
        results=(
            results
            if results is not None
            else ((_evidence(plugin_id=plugin_id, text=text),) if status == "grounded" else ())
        ),
        retrieval_id=RETRIEVAL_ID,
    )


def _context(
    *,
    service: object | None,
    principal: str = "clive",
    declared: bool = True,
    effective: bool = True,
    correlation_id: str = "request-17",
) -> PluginRuntimeContext:
    manifest = _manifest(declared=declared, effective=effective)
    context = PluginRuntimeContext(
        manifest=manifest,
        logger=_Logger(),
        config_mgr=None,
        auth_user=principal,
    )
    entitled = (
        ENTITLEMENT in manifest.entitlements
        and ENTITLEMENT in manifest.execution_policy.entitlements
    )
    object.__setattr__(
        context,
        "_knowledge_retrieval_bridge",
        plugin_knowledge_bridge(
            plugin_id=manifest.plugin_id,
            principal_username=principal,
            retrieval_service=service,
            correlation_id=correlation_id,
            entitled=entitled,
            logger=context.logger,
        ),
    )
    return context


class PluginKnowledgeRetrievalTests(unittest.TestCase):
    """Verify the narrow plugin runtime capability and security boundary."""

    def test_authorised_own_scope_retrieval_returns_immutable_evidence(self) -> None:
        service = _Service(_outcome())
        context = _context(service=service)

        result = context.retrieve_my_knowledge("minority attack plans", limit=1)

        self.assertEqual(result.status, "grounded")
        self.assertEqual(result.retrieval_id, RETRIEVAL_ID)
        self.assertEqual(result.evidence[0].chunk_id, 5)
        self.assertEqual(
            service.calls,
            [{
                "query": "minority attack plans",
                "principal_username": "clive",
                "plugin_id": "weather",
                "max_selected_chunks": 1,
                "correlation_id": "request-17",
            }],
        )
        with self.assertRaises(AttributeError):
            result.status = "changed"

    def test_router_requires_declared_and_effective_entitlement(self) -> None:
        self.assertTrue(_has_self_scope_retrieval_entitlement(_manifest()))
        self.assertFalse(
            _has_self_scope_retrieval_entitlement(_manifest(declared=False))
        )
        self.assertFalse(
            _has_self_scope_retrieval_entitlement(_manifest(effective=False))
        )

    def test_core_denials_are_controlled_for_missing_use_or_ineligibility(self) -> None:
        for reason in ("RAG_USAGE_USE_NOT_GRANTED", "PLUGIN_NOT_READY"):
            with self.subTest(reason=reason):
                outcome = replace(_outcome(status="failed"), reason_codes=(reason,))
                result = _context(service=_Service(outcome)).retrieve_my_knowledge("plans")
                self.assertEqual(result.status, "failed")
                self.assertEqual(result.reason_codes, ("not_authorised_or_ineligible",))

    def test_missing_principal_entitlement_or_service_fails_closed(self) -> None:
        cases = (
            (_context(service=_Service(_outcome()), principal=""), "authentication_required"),
            (_context(service=_Service(_outcome()), declared=False), "capability_not_entitled"),
            (_context(service=_Service(_outcome()), effective=False), "capability_not_entitled"),
            (_context(service=None), "retrieval_unavailable"),
        )
        for context, reason in cases:
            with self.subTest(reason=reason):
                result = context.retrieve_my_knowledge("plans")
                self.assertEqual(result.reason_codes, (reason,))

    def test_malformed_or_unavailable_core_response_fails_closed(self) -> None:
        malformed = _context(service=_Service({"status": "grounded"}))
        unavailable = _context(service=_Service(RuntimeError("database unavailable")))
        self.assertEqual(
            malformed.retrieve_my_knowledge("plans").reason_codes,
            ("invalid_retrieval_response",),
        )
        self.assertEqual(
            unavailable.retrieve_my_knowledge("plans").reason_codes,
            ("retrieval_unavailable",),
        )

    def test_api_has_no_scope_or_plugin_selection_parameters(self) -> None:
        parameters = inspect.signature(
            PluginRuntimeContext.retrieve_my_knowledge
        ).parameters
        for forbidden in (
            "scope_type",
            "scope_key",
            "knowledge_scope_id",
            "plugin_id",
        ):
            self.assertNotIn(forbidden, parameters)
            with self.assertRaises(TypeError):
                _context(service=_Service(_outcome())).retrieve_my_knowledge(
                    "plans", **{forbidden: "PROJECT:foo"}
                )

    def test_scope_like_query_text_is_content_not_authority(self) -> None:
        service = _Service(_outcome())
        query = "Compare this with PROJECT:foo and PLUGIN:other"

        result = _context(service=service).retrieve_my_knowledge(query)

        self.assertEqual(result.status, "grounded")
        self.assertEqual(service.calls[0]["query"], query)
        self.assertEqual(service.calls[0]["plugin_id"], "weather")

    def test_visible_context_mutation_cannot_change_bound_authority(self) -> None:
        service = _Service(_outcome())
        context = _context(service=service)
        object.__setattr__(context, "auth_user", "mallory")
        object.__setattr__(context, "manifest", replace(context.manifest, plugin_id="other"))

        result = context.retrieve_my_knowledge("plans")

        self.assertEqual(result.status, "grounded")
        self.assertEqual(service.calls[0]["principal_username"], "clive")
        self.assertEqual(service.calls[0]["plugin_id"], "weather")

    def test_forged_context_has_no_retrieval_authority(self) -> None:
        context = PluginRuntimeContext(
            manifest=_manifest(),
            logger=_Logger(),
            config_mgr=None,
            auth_user="clive",
        )
        self.assertEqual(
            context.retrieve_my_knowledge("plans").reason_codes,
            ("retrieval_unavailable",),
        )
        with self.assertRaises(TypeError):
            PluginRuntimeContext(
                manifest=_manifest(),
                logger=_Logger(),
                config_mgr=None,
                auth_user="clive",
                _knowledge_retrieval_bridge=object(),
            )

    def test_query_and_result_limits_are_bounded(self) -> None:
        context = _context(service=_Service(_outcome()))
        self.assertEqual(
            context.retrieve_my_knowledge("x" * 2049).reason_codes,
            ("query_too_long",),
        )
        for invalid_limit in (0, 7, True, 1.5):
            with self.subTest(limit=invalid_limit):
                self.assertEqual(
                    context.retrieve_my_knowledge("plans", limit=invalid_limit).reason_codes,
                    ("invalid_limit",),
                )
        long_outcome = _outcome(text="x" * (PLUGIN_KNOWLEDGE_MAX_CHUNK_CHARS + 100))
        result = _context(service=_Service(long_outcome)).retrieve_my_knowledge("plans")
        self.assertEqual(len(result.evidence[0].text), PLUGIN_KNOWLEDGE_MAX_CHUNK_CHARS)

    def test_result_scope_mismatch_or_excess_count_is_rejected(self) -> None:
        wrong_scope = _context(service=_Service(_outcome(plugin_id="other")))
        too_many = _context(
            service=_Service(
                _outcome(results=tuple(_evidence() for _ in range(2)))
            )
        )
        self.assertEqual(
            wrong_scope.retrieve_my_knowledge("plans").reason_codes,
            ("invalid_retrieval_response",),
        )
        self.assertEqual(
            too_many.retrieve_my_knowledge("plans", limit=1).reason_codes,
            ("invalid_retrieval_response",),
        )


if __name__ == "__main__":
    unittest.main()
