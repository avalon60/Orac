"""Verify the transport-neutral communications processor and legacy seam."""

# Author: Clive Bostock
# Date: 2026-09-20
# Description: Tests canonical validation, streaming, and voice NDJSON routing.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import json
import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from controller.orac import Orac
from orac_core.communications import ConversationContext
from orac_core.communications import CapabilityRestrictions
from orac_core.communications import Message
from orac_core.communications import MessageRole
from orac_core.communications import OracRequest
from orac_core.communications import OracRequestProcessor
from orac_core.communications import OracResponse
from orac_core.communications import PrincipalContext
from orac_core.communications import StreamEvent
from orac_core.communications import StreamEventKind
from orac_core.communications.adapters.ndjson import event_to_frame
from orac_core.communications.runtime import OracCommunicationsRuntime
from orac_core.communications.adapters.voice import VoiceAdapter


class _Runtime:
    """Record requests received by the processor."""

    def __init__(self) -> None:
        self.requests: list[OracRequest] = []

    async def process(self, request: OracRequest, *, event_sink=None) -> OracResponse:
        """Return a deterministic assistant response."""
        self.requests.append(request)
        return OracResponse(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            conversation_id="conv-1",
            model=request.model or "unit-model",
            message=Message(MessageRole.ASSISTANT, "Hello from Orac"),
            finish_reason="stop",
        )


def _request(*, username: str = "unit_user") -> OracRequest:
    """Build a canonical test request."""
    return OracRequest(
        request_id="req-1",
        correlation_id="corr-1",
        principal=PrincipalContext(username=username, roles=("user",)),
        conversation=ConversationContext(),
        message=Message(MessageRole.USER, "Hello"),
        source="internal",
    )


def test_internal_caller_uses_processor_without_openai_types() -> None:
    """Canonical internal callers should invoke the runtime exactly once."""
    runtime = _Runtime()
    response = asyncio.run(OracRequestProcessor(runtime).process(_request()))

    assert response.message is not None
    assert response.message.text == "Hello from Orac"
    assert runtime.requests == [_request()]


def test_legacy_orac_facade_does_not_own_the_ordered_pipeline() -> None:
    """Keep shared orchestration owned by the communications runtime."""
    assert Orac.__bases__ == (OracCommunicationsRuntime,)
    assert "_execute_ordered_pipeline" not in Orac.__dict__
    assert "_execute_ordered_pipeline" in OracCommunicationsRuntime.__dict__


def test_processor_rejects_missing_trusted_principal() -> None:
    """Untrusted requests must fail before reaching orchestration."""
    runtime = _Runtime()
    response = asyncio.run(OracRequestProcessor(runtime).process(_request(username="")))

    assert response.error is not None
    assert response.error.code == "UNAUTHORISED"
    assert runtime.requests == []


def test_processor_normalises_runtime_errors() -> None:
    """Raw runtime exceptions must not cross the communications boundary."""

    class _FailingRuntime:
        async def process(self, request, *, event_sink=None):
            raise RuntimeError("secret internal detail")

    response = asyncio.run(OracRequestProcessor(_FailingRuntime()).process(_request()))

    assert response.error is not None
    assert response.error.code == "INTERNAL_ERROR"
    assert "secret" not in response.error.message


def test_requested_model_must_remain_inside_caller_restrictions() -> None:
    """A caller model bound must be enforced before runtime selection."""
    runtime = _Runtime()
    request = _request()
    request = OracRequest(
        request_id=request.request_id,
        correlation_id=request.correlation_id,
        principal=request.principal,
        conversation=request.conversation,
        message=request.message,
        source=request.source,
        model="denied-model",
        restrictions=CapabilityRestrictions(model_ids=frozenset({"allowed-model"})),
    )

    response = asyncio.run(OracRequestProcessor(runtime).process(request))

    assert response.error is not None
    assert response.error.code == "MODEL_NOT_AUTHORISED"
    assert runtime.requests == []


def test_voice_ndjson_request_reaches_canonical_processor() -> None:
    """The existing voice-originated socket request must use the processor."""
    runtime = _Runtime()
    orchestrator = Orac.__new__(Orac)
    orchestrator.model_name = "unit-model"
    orchestrator.auth_chain = SimpleNamespace(
        authenticate=lambda _frame: SimpleNamespace(
            ok=True,
            user="voice_user",
            roles=("user",),
            reason=None,
        )
    )
    orchestrator.request_processor = OracRequestProcessor(runtime)
    frame = {
        "v": 1,
        "type": "request",
        "id": "voice-1",
        "route": "orac.prompt",
        "meta": {"channel": "voice", "client": "voice", "stream": False},
        "payload": {"messages": [{"role": "user", "content": "Hello"}]},
    }

    with patch("controller.orac.validate_frame", lambda _frame: None):
        wire = asyncio.run(orchestrator.handle_request(json.dumps(frame)))

    response = json.loads(wire)
    assert response["payload"]["content"] == "Hello from Orac"
    assert runtime.requests[0].source == "voice"
    assert runtime.requests[0].principal.username == "voice_user"


def test_voice_adapter_produces_transport_neutral_request() -> None:
    """Voice adaptation must stop at the canonical processor contract."""
    frame = {
        "v": 1,
        "type": "request",
        "id": "voice-2",
        "route": "orac.prompt",
        "meta": {"channel": "voice", "stream": True},
        "payload": {"messages": [{"role": "user", "content": "Hello"}]},
    }

    request = VoiceAdapter().to_request(
        frame,
        principal=PrincipalContext("voice_user", host_identity="frame-auth"),
    )

    assert request.source == "voice"
    assert request.message == Message(MessageRole.USER, "Hello")
    assert request.principal.host_identity == "frame-auth"


def test_voice_event_projection_preserves_presentation_metadata() -> None:
    """Legacy voice clients must retain model and playback-facing metadata."""
    frame = event_to_frame(
        StreamEvent(
            request_id="voice-3",
            correlation_id="corr-3",
            sequence=2,
            kind=StreamEventKind.TEXT_DELTA,
            delta="Hello",
            metadata={
                "model": "unit-model",
                "llm_source": "configured_default",
                "user_registration": "registered",
                "personality_code": "DEFAULT",
            },
        )
    )

    assert frame["meta"]["model"] == "unit-model"
    assert frame["meta"]["llm_source"] == "configured_default"
    assert frame["meta"]["user_registration"] == "registered"
    assert frame["meta"]["personality_code"] == "DEFAULT"
