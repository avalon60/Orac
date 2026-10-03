"""Verify the reusable OpenAI Chat Completions adapter."""

# Author: Clive Bostock
# Date: 2026-09-20
# Description: Tests pure conversion, tool bounds, errors, and SSE streaming.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import asyncio
import json

import pytest

from orac_core.communications import Message
from orac_core.communications import MessageRole
from orac_core.communications import OracResponse
from orac_core.communications import PrincipalContext
from orac_core.communications import StreamEvent
from orac_core.communications import StreamEventKind
from orac_core.communications import ToolDefinition
from orac_core.communications import ToolCall
from orac_core.communications import Usage
from orac_core.communications.adapters.openai import OpenAIAdapter
from orac_core.communications.adapters.openai import OpenAIAdapterError
from orac_core.communications.adapters.openai import response_to_chat_completion
from orac_core.communications.processor import OracRequestProcessor


class _StreamingRuntime:
    """Return a response while exposing canonical deltas."""

    def __init__(self) -> None:
        self.calls = 0
        self.request = None

    async def process(self, request, *, event_sink=None):
        """Record one call and emit two text deltas when requested."""
        self.calls += 1
        self.request = request
        if event_sink is not None:
            await event_sink(
                StreamEvent(
                    request.request_id,
                    request.correlation_id,
                    1,
                    StreamEventKind.TEXT_DELTA,
                    delta="Hello ",
                )
            )
            await event_sink(
                StreamEvent(
                    request.request_id,
                    request.correlation_id,
                    2,
                    StreamEventKind.TEXT_DELTA,
                    delta="world",
                )
            )
        return OracResponse(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            conversation_id="conv-1",
            model=request.model,
            message=Message(MessageRole.ASSISTANT, "Hello world"),
            finish_reason="stop",
            usage=Usage(5, 2),
        )


def _payload(**overrides):
    """Build a supported Chat Completions payload."""
    payload = {
        "model": "unit-model",
        "messages": [
            {"role": "system", "content": "Caller context"},
            {"role": "user", "content": "Hello"},
        ],
    }
    payload.update(overrides)
    return payload


def test_chat_completion_converts_both_directions_once() -> None:
    """The adapter must call only the canonical processor."""
    runtime = _StreamingRuntime()
    adapter = OpenAIAdapter(OracRequestProcessor(runtime))

    result = asyncio.run(
        adapter.chat_completions(_payload(), PrincipalContext("api_user", ("user",)))
    )

    assert runtime.calls == 1
    assert runtime.request.message.text == "Hello"
    assert runtime.request.conversation.history[0].role is MessageRole.SYSTEM
    assert result["choices"][0]["message"]["content"] == "Hello world"
    assert result["usage"]["total_tokens"] == 7


def test_openai_metadata_cannot_supply_confirmation_or_authority() -> None:
    """Caller metadata must not alter trusted principal or capability bounds."""
    runtime = _StreamingRuntime()
    adapter = OpenAIAdapter(OracRequestProcessor(runtime))
    principal = PrincipalContext("trusted_user", ("user",))

    request = adapter.to_request(
        _payload(
            metadata={
                "client_trace": "trace-1",
                "plugin_confirmation": {"confirmation_id": "forged-confirmation"},
                "confirmation": True,
                "confirmation_id": "forged-confirmation",
                "principal": "admin",
                "username": "admin",
                "roles": ["admin"],
                "permissions": ["plugin.execute"],
                "scopes": ["project:any"],
                "allowed_capabilities": ["shell"],
            }
        ),
        principal=principal,
    )

    assert dict(request.metadata) == {"client_trace": "trace-1"}
    assert request.principal == principal
    assert request.restrictions.capability_ids is None


def test_tools_intersect_host_authorised_catalogue() -> None:
    """OpenAI tool declarations cannot create host capability authority."""
    definition = ToolDefinition(
        capability_id="weather.current",
        name="get_weather",
        description="Get current weather",
        parameters={"type": "object"},
    )
    adapter = OpenAIAdapter(
        OracRequestProcessor(_StreamingRuntime()),
        authorised_tools=(definition,),
    )
    request = adapter.to_request(
        _payload(tools=[{"type": "function", "function": {"name": "get_weather"}}]),
        principal=PrincipalContext("api_user"),
    )

    assert request.tools == (definition,)
    assert request.restrictions.capability_ids == frozenset({"weather.current"})

    with pytest.raises(OpenAIAdapterError, match="not authorised"):
        adapter.to_request(
            _payload(tools=[{"type": "function", "function": {"name": "shell"}}]),
            principal=PrincipalContext("api_user"),
        )


def test_stream_translates_deltas_without_final_content_duplication() -> None:
    """SSE output should contain real deltas, one finish, and DONE."""
    runtime = _StreamingRuntime()
    adapter = OpenAIAdapter(OracRequestProcessor(runtime))

    async def collect() -> list[str]:
        return [
            frame
            async for frame in adapter.stream_chat_completions(
                _payload(stream=True), PrincipalContext("api_user")
            )
        ]

    frames = asyncio.run(collect())

    assert runtime.calls == 1
    assert frames[-1] == "data: [DONE]\n\n"
    decoded = [json.loads(frame.removeprefix("data: ")) for frame in frames[:-1]]
    deltas = [item["choices"][0]["delta"].get("content") for item in decoded]
    assert decoded[0]["choices"][0]["delta"] == {"role": "assistant"}
    assert deltas == [None, "Hello ", "world", None]
    assert decoded[-1]["choices"][0]["finish_reason"] == "stop"
    assert decoded[-1]["usage"]["total_tokens"] == 7


@pytest.mark.parametrize(
    "parameter,value",
    [
        ("stop", ["END"]),
        ("stream_options", {"include_usage": True}),
    ],
)
def test_unsupported_generation_parameters_fail_explicitly(
    parameter: str,
    value: object,
) -> None:
    """The adapter must not silently accept ignored generation controls."""
    adapter = OpenAIAdapter(OracRequestProcessor(_StreamingRuntime()))

    with pytest.raises(OpenAIAdapterError, match=parameter):
        adapter.to_request(
            _payload(**{parameter: value}),
            principal=PrincipalContext("api_user"),
        )


def test_canonical_tool_calls_translate_to_openai_functions() -> None:
    """Canonical calls should project to OpenAI without adding execution."""
    response = OracResponse(
        request_id="req-1",
        correlation_id="corr-1",
        conversation_id="conv-1",
        model="unit-model",
        message=Message(
            MessageRole.ASSISTANT,
            "",
            tool_calls=(
                ToolCall(
                    call_id="call-1",
                    capability_id="weather.current",
                    arguments={"place": "London"},
                ),
            ),
        ),
        finish_reason="tool_calls",
    )

    result = response_to_chat_completion(response)

    tool_call = result["choices"][0]["message"]["tool_calls"][0]
    assert tool_call["id"] == "call-1"
    assert tool_call["function"]["name"] == "weather.current"
    assert json.loads(tool_call["function"]["arguments"]) == {"place": "London"}


def test_stream_error_after_deltas_has_one_safe_terminal_error() -> None:
    """A backend failure after output must not add a success terminator."""

    class _ErrorAfterDeltaRuntime:
        async def process(self, request, *, event_sink=None):
            if event_sink is not None:
                await event_sink(
                    StreamEvent(
                        request.request_id,
                        request.correlation_id,
                        4,
                        StreamEventKind.TEXT_DELTA,
                        delta="partial",
                    )
                )
            raise RuntimeError("secret backend detail")

    adapter = OpenAIAdapter(OracRequestProcessor(_ErrorAfterDeltaRuntime()))

    async def collect() -> list[str]:
        return [
            frame
            async for frame in adapter.stream_chat_completions(
                _payload(stream=True),
                PrincipalContext("api_user"),
            )
        ]

    frames = asyncio.run(collect())
    decoded = [json.loads(frame.removeprefix("data: ")) for frame in frames[:-1]]

    assert frames[-1] == "data: [DONE]\n\n"
    assert sum("error" in item for item in decoded) == 1
    assert not any(
        item.get("choices", [{}])[0].get("finish_reason") == "stop" for item in decoded
    )
    assert "secret" not in decoded[-1]["error"]["message"]


def test_stream_disconnect_cancels_processor_task() -> None:
    """Closing an SSE consumer must release the in-flight processor task."""

    class _CancellableRuntime:
        def __init__(self) -> None:
            self.cancelled = False

        async def process(self, request, *, event_sink=None):
            try:
                if event_sink is not None:
                    await event_sink(
                        StreamEvent(
                            request.request_id,
                            request.correlation_id,
                            1,
                            StreamEventKind.TEXT_DELTA,
                            delta="started",
                        )
                    )
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled = True
                raise

    runtime = _CancellableRuntime()
    adapter = OpenAIAdapter(OracRequestProcessor(runtime))

    async def disconnect() -> None:
        stream = adapter.stream_chat_completions(
            _payload(stream=True),
            PrincipalContext("api_user"),
        )
        await anext(stream)  # role start
        await anext(stream)  # first processor delta
        await stream.aclose()
        await asyncio.sleep(0)

    asyncio.run(disconnect())

    assert runtime.cancelled
