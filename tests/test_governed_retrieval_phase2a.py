"""Tests for Phase 2A streaming-first governed retrieval."""
# Author: Clive Bostock
# Date: 2026-08-29
# Description: Verifies commit gating, tool validation, health, and safe continuation.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import time
import unittest
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from orac_core.conversation_memory import GovernedRetrievalResult  # noqa: E402
from orac_core.conversation_memory import RetrievalDomain  # noqa: E402
from orac_core.conversation_memory import RetrievalInitiator  # noqa: E402
from orac_core.conversation_memory import TrustedRetrievalContext  # noqa: E402
from orac_core.governed_retrieval import EffectiveToolModeResolver  # noqa: E402
from orac_core.governed_retrieval import GovernedRetrievalConfiguration  # noqa: E402
from orac_core.governed_retrieval import GovernedRetrievalToolCoordinator  # noqa: E402
from orac_core.governed_retrieval import ModelToolCapabilityEvidence  # noqa: E402
from orac_core.governed_retrieval import (  # noqa: E402
    REQUIRED_RETRIEVAL_UNAVAILABLE_MESSAGE,
)
from orac_core.governed_retrieval import StreamingHealthKey  # noqa: E402
from orac_core.governed_retrieval import StreamingToolHealthTracker  # noqa: E402
from orac_core.governed_retrieval import ToolDecisionMode  # noqa: E402
from orac_core.governed_retrieval import ToolStreamEvent  # noqa: E402
from orac_core.governed_retrieval import ToolStreamEventKind as Kind  # noqa: E402


@dataclass(frozen=True)
class _Evidence:
    """Small generic evidence fixture."""

    text: str
    checkpoint_id: int = 20
    conversation_id: int = 7
    message_id: int = 10


class _Mediator:
    """Capture validated retrieval calls."""

    def __init__(self) -> None:
        self.calls = []

    def retrieve(self, request, *, context):
        """Return one provenance-backed conversation result."""
        self.calls.append((request, context))
        return GovernedRetrievalResult(
            domain=request.domain,
            status="grounded",
            reason_codes=("evidence_selected",),
            evidence=(_Evidence("Documents remain the priority."),),
            provenance={"retrieval_id": "safe-id", "message_ids": (10,)},
        )


class _Connector:
    """Provider-neutral fixture with one initial and optional continuation stream."""

    def __init__(self, initial, final=()) -> None:
        self.initial = list(initial)
        self.final = list(final)
        self.invocations = []

    def stream_tool_events(self, *, messages, tools, generation_options):
        """Yield initial events when tools exist, otherwise final events."""
        self.invocations.append((messages, tools, generation_options, "stream"))
        yield from (self.initial if tools else self.final)

    def buffered_tool_events(self, *, messages, tools, generation_options):
        """Yield the same fixture events through buffered mode."""
        self.invocations.append((messages, tools, generation_options, "buffered"))
        yield from self.initial


class _SequenceConnector:
    """Return distinct required-decision attempts and one final continuation."""

    def __init__(self, attempts, final=()) -> None:
        self.attempts = [list(events) for events in attempts]
        self.final = list(final)
        self.invocations = []

    def stream_tool_events(self, *, messages, tools, generation_options):
        """Yield the next decision attempt or the grounded continuation."""
        self.invocations.append((messages, tools, generation_options, "stream"))
        if tools:
            yield from self.attempts.pop(0)
        else:
            yield from self.final

    def buffered_tool_events(self, *, messages, tools, generation_options):
        """Yield the next decision attempt in buffered mode."""
        self.invocations.append((messages, tools, generation_options, "buffered"))
        yield from self.attempts.pop(0)


class _Config:
    """ConfigManager-compatible fixture."""

    def __init__(self, values=None):
        self.values = values or {}

    def bool_config_value(self, section, key, default=False):
        return self.values.get(key, default)

    def int_config_value(self, section, key, default=0):
        return self.values.get(key, default)

    def config_value(self, section, key, default=""):
        return self.values.get(key, default)


def _context():
    return TrustedRetrievalContext(
        principal_username="clive",
        evidence_token_budget=500,
        initiator=RetrievalInitiator.MODEL_TOOL,
    )


def _tool_events(arguments='{"query":"image support","domain":"CONVERSATION"}'):
    return [
        ToolStreamEvent(Kind.TOOL_CALL_START, call_id="call-1", tool_name="retrieve"),
        ToolStreamEvent(
            Kind.TOOL_CALL_ARGUMENT_DELTA,
            call_id="call-1",
            tool_name="retrieve",
            arguments_delta=arguments[:20],
        ),
        ToolStreamEvent(
            Kind.TOOL_CALL_ARGUMENT_DELTA,
            call_id="call-1",
            tool_name="retrieve",
            arguments_delta=arguments[20:],
        ),
        ToolStreamEvent(Kind.TOOL_CALL_COMPLETED, call_id="call-1", tool_name="retrieve"),
        ToolStreamEvent(Kind.ASSISTANT_COMPLETION, finish_reason="tool_calls"),
    ]


class GovernedRetrievalConfigurationTests(unittest.TestCase):
    """Verify host-only validated commit-gate configuration."""

    def test_defaults_load_and_invalid_bounds_fail(self):
        config = GovernedRetrievalConfiguration.from_config(_Config())
        self.assertTrue(config.enabled)
        self.assertTrue(config.domain_discovery_enabled)
        self.assertFalse(config.domain_discovery_shadow_mode)
        self.assertEqual(config.min_effective_context_tokens, 32768)
        self.assertEqual(config.stream_commit_delay_ms, 350)
        self.assertEqual(config.stream_commit_max_characters, 128)
        with self.assertRaises(ValueError):
            GovernedRetrievalConfiguration(stream_commit_delay_ms=99)
        with self.assertRaises(ValueError):
            GovernedRetrievalConfiguration(stream_commit_max_characters=513)
        with self.assertRaises(ValueError):
            GovernedRetrievalConfiguration(
                domain_discovery_enabled=True,
                domain_discovery_shadow_mode=True,
            )


class GovernedRetrievalCoordinatorTests(unittest.TestCase):
    """Exercise direct, early-tool, late-tool, and malformed paths."""

    def setUp(self):
        self.mediator = _Mediator()
        self.config = GovernedRetrievalConfiguration(
            enabled=True,
            stream_commit_delay_ms=350,
            stream_commit_max_characters=32,
        )
        self.coordinator = GovernedRetrievalToolCoordinator(
            mediator=self.mediator,
            configuration=self.config,
        )

    def _run(self, connector, mode=ToolDecisionMode.STREAMING):
        execution = self.coordinator.begin(
            connector=connector,
            messages=[{"role": "user", "content": "question"}],
            mode=mode,
            allowed_domains=(RetrievalDomain.CONVERSATION,),
            context=_context(),
        )
        visible = "".join(execution.stream())
        return visible, execution.result

    def test_direct_answer_streams_without_second_invocation(self):
        connector = _Connector(
            [
                ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text="A" * 32),
                ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text=" done"),
                ToolStreamEvent(Kind.ASSISTANT_COMPLETION, finish_reason="stop"),
            ]
        )
        visible, result = self._run(connector)
        self.assertEqual(visible, "A" * 32 + " done")
        self.assertEqual(len(connector.invocations), 1)
        self.assertFalse(result.retrieval_executed)

    def test_time_threshold_commits_while_provider_is_idle(self):
        class _TimedConnector(_Connector):
            def stream_tool_events(inner_self, *, messages, tools, generation_options):
                inner_self.invocations.append((messages, tools, generation_options, "stream"))
                yield ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text="first ")
                time.sleep(0.20)
                yield ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text="second")
                yield ToolStreamEvent(Kind.ASSISTANT_COMPLETION, finish_reason="stop")

        coordinator = GovernedRetrievalToolCoordinator(
            mediator=self.mediator,
            configuration=GovernedRetrievalConfiguration(
                enabled=True,
                stream_commit_delay_ms=100,
                stream_commit_max_characters=32,
            ),
        )
        execution = coordinator.begin(
            connector=_TimedConnector([]),
            messages=[{"role": "user", "content": "question"}],
            mode=ToolDecisionMode.STREAMING,
            allowed_domains=(RetrievalDomain.CONVERSATION,),
            context=_context(),
        )
        stream = execution.stream()
        started = time.monotonic()
        self.assertEqual(next(stream), "first ")
        self.assertLess(time.monotonic() - started, 0.18)
        self.assertEqual("".join(stream), "second")

    def test_early_tool_discards_buffer_and_streams_only_grounded_answer(self):
        connector = _Connector(
            [ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text="Let me check. ")]
            + _tool_events(),
            [
                ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text="Documents come first."),
                ToolStreamEvent(Kind.ASSISTANT_COMPLETION, finish_reason="stop"),
            ],
        )
        visible, result = self._run(connector)
        self.assertEqual(visible, "Documents come first.")
        self.assertEqual(len(self.mediator.calls), 1)
        self.assertTrue(result.retrieval_executed)
        self.assertEqual(result.tool_call_timing, "EARLY")
        self.assertEqual(connector.invocations[1][1], [])

    def test_required_retrieval_uses_compact_decision_then_full_grounded_context(
        self,
    ) -> None:
        connector = _SequenceConnector(
            [
                [
                    ToolStreamEvent(
                        Kind.ASSISTANT_TEXT_DELTA,
                        text="I can answer without checking.",
                    ),
                    ToolStreamEvent(Kind.ASSISTANT_COMPLETION, finish_reason="stop"),
                ],
                _tool_events(),
            ],
            [
                ToolStreamEvent(
                    Kind.ASSISTANT_TEXT_DELTA,
                    text="Grounded from authorised evidence.",
                ),
                ToolStreamEvent(Kind.ASSISTANT_COMPLETION, finish_reason="stop"),
            ],
        )
        execution = self.coordinator.begin(
            connector=connector,
            messages=[{"role": "user", "content": "What is the AI OS?"}],
            answer_messages=[
                {"role": "system", "content": "ordinary policy"},
                {"role": "user", "content": "COMPLETE FLATTENED PROMPT"},
            ],
            mode=ToolDecisionMode.STREAMING,
            allowed_domains=(RetrievalDomain.CONVERSATION,),
            context=_context(),
            retrieval_required=True,
            retrieval_requirement_reasons=("SEMANTIC_DOMAIN_MATCH",),
        )

        self.assertEqual(
            "".join(execution.stream()),
            "Grounded from authorised evidence.",
        )
        self.assertEqual(len(connector.invocations), 3)
        self.assertEqual(
            connector.invocations[0][0][-1]["content"],
            "What is the AI OS?",
        )
        self.assertNotIn(
            "COMPLETE FLATTENED PROMPT",
            str(connector.invocations[0][0]),
        )
        self.assertIn(
            "host has determined that retrieval is required",
            str(connector.invocations[0][0]).lower(),
        )
        self.assertIn(
            "retrieval remains required",
            str(connector.invocations[1][0]).lower(),
        )
        self.assertIn(
            "COMPLETE FLATTENED PROMPT",
            str(connector.invocations[-1][0]),
        )
        self.assertEqual(connector.invocations[-1][1], [])
        self.assertTrue(execution.result.retrieval_executed)
        self.assertEqual(execution.result.decision_attempt_count, 2)
        self.assertEqual(
            execution.result.discarded_decision_characters,
            len("I can answer without checking."),
        )
        self.assertEqual(execution.result.characters_before_commit, 0)

    def test_required_retrieval_never_commits_prose_after_two_no_tool_attempts(
        self,
    ) -> None:
        connector = _SequenceConnector(
            [
                [ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text="First answer.")],
                [ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text="Second answer.")],
            ]
        )
        execution = self.coordinator.begin(
            connector=connector,
            messages=[{"role": "user", "content": "Check your knowledge base."}],
            mode=ToolDecisionMode.STREAMING,
            allowed_domains=(RetrievalDomain.CONVERSATION,),
            context=_context(),
            retrieval_required=True,
            retrieval_requirement_reasons=("EXPLICIT_LOCAL_RETRIEVAL_INTENT",),
        )

        self.assertEqual(
            "".join(execution.stream()),
            REQUIRED_RETRIEVAL_UNAVAILABLE_MESSAGE,
        )
        self.assertEqual(len(connector.invocations), 2)
        self.assertFalse(execution.result.retrieval_executed)
        self.assertEqual(execution.result.decision_attempt_count, 2)
        self.assertEqual(execution.result.characters_before_commit, 0)
        self.assertEqual(
            execution.result.discarded_decision_characters,
            len("First answer.Second answer."),
        )
        self.assertIn(
            "REQUIRED_TOOL_CALL_NOT_EMITTED",
            execution.result.reason_codes,
        )

    def test_required_retrieval_discards_prose_before_a_valid_call(self) -> None:
        connector = _SequenceConnector(
            [[ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text="Let me guess. ")] + _tool_events()],
            [ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text="Grounded answer.")],
        )
        execution = self.coordinator.begin(
            connector=connector,
            messages=[{"role": "user", "content": "question"}],
            mode=ToolDecisionMode.STREAMING,
            allowed_domains=(RetrievalDomain.CONVERSATION,),
            context=_context(),
            retrieval_required=True,
            retrieval_requirement_reasons=("SEMANTIC_DOMAIN_MATCH",),
        )

        self.assertEqual("".join(execution.stream()), "Grounded answer.")
        self.assertEqual(execution.result.decision_attempt_count, 1)
        self.assertEqual(
            execution.result.discarded_decision_characters,
            len("Let me guess. "),
        )
        self.assertEqual(execution.result.characters_before_commit, 0)

    def test_late_tool_is_ignored_when_provider_continues(self):
        connector = _Connector(
            [ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text="A" * 32)]
            + _tool_events()
            + [
                ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text=" suffix"),
                ToolStreamEvent(Kind.ASSISTANT_COMPLETION, finish_reason="stop"),
            ]
        )
        visible, result = self._run(connector)
        self.assertEqual(visible, "A" * 32 + " suffix")
        self.assertFalse(result.retrieval_executed)
        self.assertFalse(result.continuation_recovery_used)
        self.assertEqual(len(connector.invocations), 1)

    def test_late_tool_termination_uses_suffix_only_recovery(self):
        connector = _Connector(
            [ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text="A" * 32)]
            + _tool_events(),
            [
                ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text=" suffix"),
                ToolStreamEvent(Kind.ASSISTANT_COMPLETION, finish_reason="stop"),
            ],
        )
        visible, result = self._run(connector)
        self.assertEqual(visible, "A" * 32 + " suffix")
        self.assertFalse(result.retrieval_executed)
        self.assertTrue(result.continuation_recovery_used)
        self.assertEqual(len(connector.invocations), 2)

    def test_malformed_and_extra_fields_never_execute(self):
        for arguments in (
            '{"query":',
            '{"query":"x","domain":"CONVERSATION","user_id":123}',
            '{"query":"x","domain":"UNKNOWN"}',
        ):
            with self.subTest(arguments=arguments):
                self.mediator.calls.clear()
                connector = _Connector(
                    _tool_events(arguments),
                    [
                        ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text="Safe fallback."),
                        ToolStreamEvent(Kind.ASSISTANT_COMPLETION, finish_reason="stop"),
                    ],
                )
                visible, result = self._run(connector)
                self.assertEqual(visible, "Safe fallback.")
                self.assertFalse(result.retrieval_executed)
                self.assertEqual(self.mediator.calls, [])

    def test_multiple_tool_calls_never_execute(self):
        events = _tool_events()[:-1] + [
            ToolStreamEvent(
                Kind.TOOL_CALL_START,
                call_id="call-2",
                call_index=1,
                tool_name="retrieve",
            ),
            ToolStreamEvent(
                Kind.TOOL_CALL_ARGUMENT_DELTA,
                call_id="call-2",
                call_index=1,
                tool_name="retrieve",
                arguments_delta='{"query":"x","domain":"CONVERSATION"}',
            ),
            ToolStreamEvent(
                Kind.TOOL_CALL_COMPLETED,
                call_id="call-2",
                call_index=1,
                tool_name="retrieve",
            ),
            ToolStreamEvent(Kind.ASSISTANT_COMPLETION, finish_reason="tool_calls"),
        ]
        connector = _Connector(
            events,
            [ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text="Safe fallback.")],
        )
        visible, result = self._run(connector)
        self.assertEqual(visible, "Safe fallback.")
        self.assertFalse(result.retrieval_executed)
        self.assertEqual(self.mediator.calls, [])

    def test_model_arguments_cannot_change_commit_gate(self):
        arguments = (
            '{"query":"x","domain":"CONVERSATION",'
            '"stream_commit_delay_ms":0}'
        )
        connector = _Connector(
            _tool_events(arguments),
            [ToolStreamEvent(Kind.ASSISTANT_TEXT_DELTA, text="Fallback.")],
        )
        _, result = self._run(connector)
        self.assertFalse(result.retrieval_executed)
        self.assertEqual(self.config.stream_commit_delay_ms, 350)

    def test_all_domains_share_the_final_evidence_character_bound(self):
        """Federated services retain one bounded model-facing serialization."""
        for domain in RetrievalDomain:
            with self.subTest(domain=domain.value):
                payload = self.coordinator._serialise_tool_result(
                    GovernedRetrievalResult(
                        domain=domain,
                        status="grounded",
                        reason_codes=("evidence_selected",),
                        evidence=(_Evidence("x" * 1000),),
                        provenance={"retrieval_id": "safe-id"},
                    ),
                    max_evidence_characters=128,
                )
                decoded = json.loads(payload)
                self.assertEqual(decoded["domain"], domain.value)
                self.assertEqual(len(decoded["evidence"][0]["text"]), 128)
                self.assertIn(
                    "Fresh authorised retrieved evidence supersedes conflicting "
                    "previous assistant statements.",
                    decoded["instruction"],
                )
                self.assertIn(
                    "using only the retrieved evidence",
                    decoded["instruction"],
                )
                self.assertIn(
                    "do not fill gaps from prior knowledge",
                    decoded["instruction"],
                )


class GovernedRetrievalCapabilityHealthTests(unittest.TestCase):
    """Keep governed evidence immutable while health suppresses streaming."""

    def test_health_suppression_selects_buffered_and_recovers(self):
        now = [0.0]
        tracker = StreamingToolHealthTracker(clock=lambda: now[0])
        resolver = EffectiveToolModeResolver(health_tracker=tracker)
        key = StreamingHealthKey("ollama", "runtime", "adapter-v1", 3, "rev")
        evidence = ModelToolCapabilityEvidence(True, True, "rev")
        mode, _ = resolver.resolve(
            enabled=True,
            evidence=evidence,
            provider_structured_supported=True,
            provider_streamed_supported=True,
            health_key=key,
            authority_available=True,
            context_safe=True,
        )
        self.assertEqual(mode, ToolDecisionMode.STREAMING)
        for _ in range(3):
            tracker.record(key, healthy=False, reason_code="LATE_TOOL_RATE_HIGH")
        mode, reason = resolver.resolve(
            enabled=True,
            evidence=evidence,
            provider_structured_supported=True,
            provider_streamed_supported=True,
            health_key=key,
            authority_available=True,
            context_safe=True,
        )
        self.assertEqual(mode, ToolDecisionMode.BUFFERED)
        self.assertEqual(reason, "LATE_TOOL_RATE_HIGH")
        self.assertTrue(evidence.streamed_structured_tool_calling)
        now[0] = 301.0
        mode, _ = resolver.resolve(
            enabled=True,
            evidence=evidence,
            provider_structured_supported=True,
            provider_streamed_supported=True,
            health_key=key,
            authority_available=True,
            context_safe=True,
        )
        self.assertEqual(mode, ToolDecisionMode.STREAMING)
        tracker.record(key, healthy=True, reason_code="RECOVERY_PROBE_PASSED")
        mode, _ = resolver.resolve(
            enabled=True,
            evidence=evidence,
            provider_structured_supported=True,
            provider_streamed_supported=True,
            health_key=key,
            authority_available=True,
            context_safe=True,
        )
        self.assertEqual(mode, ToolDecisionMode.STREAMING)


if __name__ == "__main__":
    unittest.main()
