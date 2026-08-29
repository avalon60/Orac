"""Tests for retained, governed, provenance-backed conversational memory."""

# Author: Clive Bostock
# Date: 2026-08-28
# Description: Verifies materialisation, direct retrieval, mediation, and policy separation.

from __future__ import annotations

import inspect
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_routing.embeddings import EmbeddingProvider  # noqa: E402
from orac_core.conversation_memory import (  # noqa: E402
    ConversationMemoryMaterialisationService,
    ConversationMemoryRetrievalService,
    HostRetrievalMediator,
    LogicalRetrievalRequest,
    MemoryIntentPolicy,
    OllamaConversationEmbeddingProvider,
    RetrievalDomain,
    RetrievalInitiator,
    TrustedRetrievalContext,
)


class ConversationEmbeddingProviderTests(unittest.TestCase):
    """Validate the structured local semantic embedding boundary."""

    @patch("orac_core.conversation_memory.embeddings.requests.post")
    def test_ollama_provider_uses_structured_embed_response(self, post: Mock) -> None:
        """Valid provider output is returned without wire-format leakage."""
        response = Mock()
        response.json.return_value = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
        post.return_value = response
        provider = OllamaConversationEmbeddingProvider(
            service_url="http://localhost:11434/",
            model_id="semantic-test",
            dimensions=2,
        )

        vectors = provider.embed_texts(["one", "two"])

        self.assertEqual(vectors, [[0.1, 0.2], [0.3, 0.4]])
        post.assert_called_once_with(
            "http://localhost:11434/api/embed",
            json={"model": "semantic-test", "input": ["one", "two"]},
            timeout=(5.0, 30.0),
        )
        response.raise_for_status.assert_called_once_with()

    @patch("orac_core.conversation_memory.embeddings.requests.post")
    def test_ollama_provider_rejects_dimension_mismatch(self, post: Mock) -> None:
        """A response incompatible with the pinned profile fails closed."""
        response = Mock()
        response.json.return_value = {"embeddings": [[0.1]]}
        post.return_value = response
        provider = OllamaConversationEmbeddingProvider(
            service_url="http://localhost:11434",
            model_id="semantic-test",
            dimensions=2,
        )

        with self.assertRaisesRegex(ValueError, "dimensions"):
            provider.embed_texts(["one"])


class _KeywordEmbeddingProvider(EmbeddingProvider):
    """Small deterministic semantic fixture for acceptance tests."""

    @property
    def model_id(self) -> str:
        """Return the fixture profile identifier."""
        return "keyword-test-v1"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Represent relevant subject terms in a fixed vector."""
        terms = ("image", "support", "document", "email")
        return [
            [float(text.lower().count(term)) for term in terms]
            for text in texts
        ]


class _Config:
    """Minimal enabled worker configuration fixture."""

    def bool_config_value(self, section, key, default=False):
        """Return enabled only for the conversation-memory section."""
        return section == "conversation_memory" and key == "enabled"

    def int_config_value(self, section, key, default=0):
        """Return compact deterministic worker limits."""
        values = {
            "checkpoint_exchange_count": 1,
            "batch_size": 1,
            "max_attempts": 3,
            "embedding_dimensions": 4,
        }
        return values.get(key, default)

    def config_value(self, section, key, default=""):
        """Return the configured embedding profile where required."""
        if key == "embedding_model_id":
            return "keyword-test-v1"
        return default


class _MemoryRepository:
    """In-memory authoritative records plus derived checkpoint fixture."""

    def __init__(self) -> None:
        self.principal = "clive"
        self.sources = [
            {
                "message_id": 10,
                "conversation_id": 7,
                "turn_index": 2,
                "role": "user",
                "content_text": (
                    "Image processing is not currently a priority for Orac; "
                    "support for the main document formats is the focus."
                ),
                "row_version": 1,
            },
            {
                "message_id": 11,
                "conversation_id": 7,
                "turn_index": 3,
                "role": "assistant",
                "content_text": "Agreed; document format support comes first.",
                "row_version": 1,
            },
        ]
        self.embeddings = {}
        self.checkpoint = None
        self._request_available = True

    def reconcile_eligible_ranges(self, **kwargs):
        """Represent an already enqueued deterministic range."""
        del kwargs
        return 0

    def next_request_id(self):
        """Return one pending request."""
        if not self._request_available:
            return None
        self._request_available = False
        return 1

    def load_request_sources(self, request_id):
        """Return authoritative ordered source messages."""
        self.assert_request(request_id)
        return list(self.sources)

    def assert_request(self, request_id):
        """Validate the fixture request identity."""
        if request_id != 1:
            raise LookupError(request_id)

    def ensure_message_embedding(self, **kwargs):
        """Persist an embedding keyed by authoritative message identity."""
        self.embeddings[kwargs["message_id"]] = tuple(kwargs["embedding"])

    def complete_request(self, **kwargs):
        """Persist an immutable checkpoint and exact lineage."""
        self.checkpoint = dict(kwargs)
        return 20

    def record_failure(self, **kwargs):
        """Fail the fixture loudly if materialisation unexpectedly fails."""
        raise AssertionError(kwargs)

    def load_summary_candidates(self, *, principal_username, **kwargs):
        """Return checkpoints only to the owning principal."""
        del kwargs
        if principal_username != self.principal or self.checkpoint is None:
            return []
        return [
            {
                "checkpoint_id": 20,
                "conversation_id": 7,
                "first_turn_index": 2,
                "last_turn_index": 3,
                "summary_text": self.checkpoint["summary_text"],
                "summary_embedding": self.checkpoint["summary_embedding"],
                "embedding_model": "keyword-test-v1",
                "prompt_version": "conversation-v1",
                "source_digest": self.checkpoint["source_digest"],
            }
        ]

    def load_source_candidates(self, *, principal_username, checkpoint_ids, **kwargs):
        """Return lineage-backed source evidence only to its owner."""
        del kwargs
        if principal_username != self.principal or checkpoint_ids != (20,):
            return []
        lineage_by_message = {
            item["message_id"]: item for item in self.checkpoint["source_lineage"]
        }
        rows = []
        for position, source in enumerate(self.sources, start=1):
            lineage = lineage_by_message[source["message_id"]]
            rows.append(
                {
                    "checkpoint_id": 20,
                    "conversation_id": 7,
                    "message_id": source["message_id"],
                    "source_position": position,
                    "turn_index": source["turn_index"],
                    "role": source["role"],
                    "source_text": source["content_text"],
                    "message_row_version": source["row_version"],
                    "source_content_sha256": lineage["source_content_sha256"],
                    "embedding": self.embeddings[source["message_id"]],
                }
            )
        return rows


class ConversationMemoryTests(unittest.TestCase):
    """Exercise the Phase 1 materialisation and retrieval contracts."""

    def setUp(self) -> None:
        """Materialise one prior conversation before every retrieval test."""
        self.repository = _MemoryRepository()
        self.embedding_provider = _KeywordEmbeddingProvider()
        worker = ConversationMemoryMaterialisationService(
            config_mgr=_Config(),
            repository=self.repository,
            embedding_provider=self.embedding_provider,
        )
        worker.tick(None)
        self.assertEqual(worker.last_checkpoint_id, 20)
        self.service = ConversationMemoryRetrievalService(
            repository=self.repository,
            embedding_provider=self.embedding_provider,
            min_summary_score=0.1,
            min_source_score=0.1,
        )

    def test_trusted_host_can_retrieve_without_memory_intent_policy(self) -> None:
        """Direct service use retains principal and provenance protections."""
        request = LogicalRetrievalRequest(
            query="What did we decide about image support?",
            domain=RetrievalDomain.CONVERSATION,
        )
        context = TrustedRetrievalContext(
            principal_username="clive",
            evidence_token_budget=500,
            current_conversation_id=9,
            initiator=RetrievalInitiator.DIRECT_HOST,
        )

        outcome = self.service.retrieve(request, context=context)

        self.assertEqual(outcome.status, "grounded")
        self.assertIn("Image processing is not currently", outcome.evidence[0].text)
        self.assertEqual(outcome.provenance.checkpoint_ids, (20,))
        self.assertEqual(outcome.provenance.conversation_ids, (7,))
        self.assertEqual(outcome.provenance.message_ids, (10, 11))
        self.assertEqual(outcome.provenance.initiator, RetrievalInitiator.DIRECT_HOST)

    def test_another_principal_cannot_infer_conversation_memory(self) -> None:
        """Cross-principal retrieval is indistinguishable from absent evidence."""
        outcome = self.service.retrieve(
            LogicalRetrievalRequest("image support", RetrievalDomain.CONVERSATION),
            context=TrustedRetrievalContext(
                principal_username="mallory",
                evidence_token_budget=500,
            ),
        )

        self.assertEqual(outcome.status, "no_evidence")
        self.assertEqual(outcome.reason_codes, ("no_relevant_checkpoint",))
        self.assertEqual(outcome.evidence, ())
        self.assertIsNone(outcome.provenance)

    def test_explicit_policy_is_only_a_mediator_caller(self) -> None:
        """The conservative phrase policy feeds the independent service seam."""
        decision = MemoryIntentPolicy().evaluate(
            "What did we decide about image support?"
        )
        self.assertTrue(decision.retrieve)
        mediator = HostRetrievalMediator(conversation_service=self.service)
        result = mediator.retrieve(
            LogicalRetrievalRequest(decision.query, RetrievalDomain.CONVERSATION),
            context=TrustedRetrievalContext(
                principal_username="clive",
                evidence_token_budget=500,
                initiator=RetrievalInitiator.EXPLICIT_POLICY,
            ),
        )
        self.assertEqual(result.status, "grounded")
        self.assertEqual(result.provenance["initiator"], "EXPLICIT_POLICY")

    def test_service_module_does_not_depend_on_phrase_policy(self) -> None:
        """Static dependency direction prevents keyword detection becoming core."""
        source = inspect.getsource(inspect.getmodule(ConversationMemoryRetrievalService))
        self.assertNotIn("MemoryIntentPolicy", source)
        self.assertNotIn("what did we decide", source.lower())

    def test_unsupported_domain_fails_closed(self) -> None:
        """Phase 1 does not route PROJECT through conversation retrieval."""
        result = HostRetrievalMediator(conversation_service=self.service).retrieve(
            LogicalRetrievalRequest("plugin architecture", RetrievalDomain.PROJECT),
            context=TrustedRetrievalContext(
                principal_username="clive",
                evidence_token_budget=500,
            ),
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.reason_codes, ("retrieval_domain_not_enabled",))

    def test_recent_message_exclusion_prevents_duplicate_context(self) -> None:
        """Evidence already in live history is not reinserted as memory."""
        outcome = self.service.retrieve(
            LogicalRetrievalRequest("image support", RetrievalDomain.CONVERSATION),
            context=TrustedRetrievalContext(
                principal_username="clive",
                evidence_token_budget=500,
                excluded_message_ids=(10,),
            ),
        )
        self.assertEqual(tuple(item.message_id for item in outcome.evidence), (11,))

    def test_live_context_maintenance_never_calls_destructive_pruning(self) -> None:
        """Leaving prompt history does not delete persisted messages."""
        controller_source = (
            PROJECT_ROOT / "src/controller/orac.py"
        ).read_text(encoding="utf-8")
        method_source = controller_source.split(
            "    def _maybe_prune(", maxsplit=1
        )[1].split("\n    def ", maxsplit=1)[0]
        self.assertNotIn(".prune_context(", method_source)
        self.assertIn("without destructive context pruning", method_source)


if __name__ == "__main__":
    unittest.main()
