"""Adapt OpenAI Chat Completions payloads to canonical Orac requests."""

# Author: Clive Bostock
# Date: 2026-09-20
# Description: Provides pure wire conversion and a processor-only facade.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import replace
from typing import Any

from orac_core.communications.models import CapabilityRestrictions
from orac_core.communications.models import ConversationContext
from orac_core.communications.models import Message
from orac_core.communications.models import MessageRole
from orac_core.communications.models import OracRequest
from orac_core.communications.models import OracResponse
from orac_core.communications.models import PrincipalContext
from orac_core.communications.models import ProcessingError
from orac_core.communications.models import StreamEventKind
from orac_core.communications.models import ToolDefinition
from orac_core.communications.models import bounded_metadata
from orac_core.communications.processor import OracRequestProcessor

_UNSUPPORTED_GENERATION_PARAMETERS = frozenset(
    {
        "audio",
        "frequency_penalty",
        "function_call",
        "functions",
        "logit_bias",
        "logprobs",
        "max_completion_tokens",
        "parallel_tool_calls",
        "prediction",
        "presence_penalty",
        "reasoning_effort",
        "service_tier",
        "stop",
        "store",
        "stream_options",
        "top_logprobs",
        "verbosity",
        "web_search_options",
    }
)


class OpenAIAdapterError(ValueError):
    """Represent a safe OpenAI payload validation failure."""

    def __init__(self, code: str, message: str) -> None:
        """Initialise a stable validation code and safe message."""
        super().__init__(message)
        self.code = code


class OpenAIAdapter:
    """Translate Chat Completions while always invoking the core processor."""

    def __init__(
        self,
        processor: OracRequestProcessor,
        *,
        authorised_tools: Sequence[ToolDefinition] = (),
    ) -> None:
        """Initialise the adapter with processor and host-authorised tools."""
        self._processor = processor
        self._authorised_tools = {
            definition.name: definition for definition in authorised_tools
        }

    async def chat_completions(
        self,
        payload: Mapping[str, Any],
        principal: PrincipalContext,
        context: ConversationContext | None = None,
        restrictions: CapabilityRestrictions | None = None,
    ) -> dict[str, Any]:
        """Process one non-streaming Chat Completions request."""
        request = self.to_request(
            payload,
            principal=principal,
            context=context,
            restrictions=restrictions,
        )
        response = await self._processor.process(request)
        return response_to_chat_completion(response)

    async def stream_chat_completions(
        self,
        payload: Mapping[str, Any],
        principal: PrincipalContext,
        context: ConversationContext | None = None,
        restrictions: CapabilityRestrictions | None = None,
    ) -> AsyncIterator[str]:
        """Yield SSE frames from canonical deltas with one terminal marker."""
        request = replace(
            self.to_request(
                payload,
                principal=principal,
                context=context,
                restrictions=restrictions,
            ),
            stream=True,
        )
        completion_id = f"chatcmpl-{request.request_id}"
        created = int(time.time())
        yield _sse_frame(
            _chat_chunk(
                completion_id=completion_id,
                created=created,
                model=request.model,
                delta={"role": "assistant"},
                finish_reason=None,
            )
        )
        async for event in self._processor.stream(request):
            if event.kind is StreamEventKind.TEXT_DELTA and event.delta:
                yield _sse_frame(
                    _chat_chunk(
                        completion_id=completion_id,
                        created=created,
                        model=request.model,
                        delta={"content": event.delta},
                        finish_reason=None,
                    )
                )
            elif event.kind is StreamEventKind.ERROR and event.error is not None:
                yield _sse_frame({"error": _openai_error(event.error)})
            elif event.kind is StreamEventKind.COMPLETE:
                finish_reason = (
                    event.result.finish_reason if event.result is not None else "stop"
                )
                chunk = _chat_chunk(
                    completion_id=completion_id,
                    created=created,
                    model=(
                        event.result.model
                        if event.result is not None
                        else request.model
                    ),
                    delta={},
                    finish_reason=finish_reason,
                )
                if event.result is not None and event.result.usage is not None:
                    chunk["usage"] = _usage_payload(event.result.usage)
                yield _sse_frame(chunk)
        yield "data: [DONE]\n\n"

    def to_request(
        self,
        payload: Mapping[str, Any],
        *,
        principal: PrincipalContext,
        context: ConversationContext | None = None,
        restrictions: CapabilityRestrictions | None = None,
    ) -> OracRequest:
        """Convert a supported Chat Completions payload to canonical form."""
        if payload.get("n", 1) != 1:
            raise OpenAIAdapterError("unsupported_parameter", "Only n=1 is supported.")
        if payload.get("response_format") or payload.get("modalities"):
            raise OpenAIAdapterError(
                "unsupported_parameter",
                "Structured or multimodal output is not supported.",
            )
        unsupported = sorted(
            key
            for key in _UNSUPPORTED_GENERATION_PARAMETERS
            if key in payload and payload[key] is not None
        )
        if unsupported:
            raise OpenAIAdapterError(
                "unsupported_parameter",
                "Unsupported generation parameter(s): " + ", ".join(unsupported),
            )
        tool_choice = payload.get("tool_choice")
        if tool_choice not in (None, "auto"):
            raise OpenAIAdapterError(
                "unsupported_parameter",
                "Only automatic host-mediated tool choice is supported.",
            )
        model = str(payload.get("model") or "").strip()
        if not model:
            raise OpenAIAdapterError("invalid_request_error", "Model is required.")
        messages = _messages(payload.get("messages"))
        current_index = next(
            (
                index
                for index in range(len(messages) - 1, -1, -1)
                if messages[index].role is MessageRole.USER
            ),
            None,
        )
        if current_index is None:
            raise OpenAIAdapterError(
                "invalid_request_error", "A user message is required."
            )
        current = messages[current_index]
        caller_history = messages[:current_index]
        base_context = context or ConversationContext()
        # Explicit host context wins for identity/session. Caller history is only
        # request-local evidence and cannot replace host system policy.
        conversation = replace(
            base_context,
            history=base_context.history + caller_history,
        )
        tools = self._map_tools(payload.get("tools"))
        request_id = uuid.uuid4().hex
        metadata_value = payload.get("metadata")
        metadata = dict(metadata_value) if isinstance(metadata_value, Mapping) else {}
        for key in ("max_tokens", "seed", "temperature", "top_p"):
            if payload.get(key) is not None:
                metadata[key] = _validated_generation_value(key, payload[key])
        requested_capabilities = frozenset(tool.capability_id for tool in tools)
        return OracRequest(
            request_id=request_id,
            correlation_id=request_id,
            principal=principal,
            conversation=conversation,
            message=current,
            source="openai.chat_completions",
            stream=bool(payload.get("stream")),
            model=model,
            metadata=bounded_metadata(metadata),
            restrictions=(
                restrictions
                if restrictions is not None
                else CapabilityRestrictions(
                    capability_ids=requested_capabilities or None,
                    model_ids=(None if model == "orac" else frozenset({model})),
                )
            ),
            tools=tools,
        )

    def _map_tools(self, value: object) -> tuple[ToolDefinition, ...]:
        """Intersect requested tools with the host-authorised catalogue."""
        if value is None:
            return ()
        if not isinstance(value, list):
            raise OpenAIAdapterError("invalid_request_error", "Tools must be an array.")
        selected: list[ToolDefinition] = []
        for item in value:
            if not isinstance(item, Mapping) or item.get("type") != "function":
                raise OpenAIAdapterError(
                    "unsupported_parameter", "Only function tools are supported."
                )
            function = item.get("function")
            function = function if isinstance(function, Mapping) else {}
            name = str(function.get("name") or "").strip()
            authorised = self._authorised_tools.get(name)
            if authorised is None:
                raise OpenAIAdapterError(
                    "tool_not_authorised", f"Tool '{name}' is not authorised."
                )
            selected.append(authorised)
        return tuple(selected)


def response_to_chat_completion(response: OracResponse) -> dict[str, Any]:
    """Convert a canonical response to an OpenAI-compatible object."""
    if response.error is not None:
        return {"error": _openai_error(response.error)}
    content = response.message.text if response.message is not None else ""
    assistant_message: dict[str, Any] = {
        "role": "assistant",
        "content": content,
    }
    if response.message is not None and response.message.tool_calls:
        assistant_message["tool_calls"] = [
            {
                "id": call.call_id,
                "type": "function",
                "function": {
                    "name": call.capability_id,
                    "arguments": json.dumps(dict(call.arguments), ensure_ascii=False),
                },
            }
            for call in response.message.tool_calls
        ]
    result: dict[str, Any] = {
        "id": f"chatcmpl-{response.request_id}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": response.model,
        "choices": [
            {
                "index": 0,
                "message": assistant_message,
                "finish_reason": response.finish_reason,
            }
        ],
    }
    if response.usage is not None:
        result["usage"] = _usage_payload(response.usage)
    return result


def serialise_models(models: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Serialise a host-authorised runtime catalogue for a future endpoint."""
    return {
        "object": "list",
        "data": [
            {
                "id": str(model["id"]),
                "object": "model",
                "owned_by": str(model.get("owned_by") or "orac"),
            }
            for model in models
            if model.get("id")
        ],
    }


def _messages(value: object) -> tuple[Message, ...]:
    """Parse text-only OpenAI messages without accepting wire authority."""
    if not isinstance(value, list) or not value:
        raise OpenAIAdapterError(
            "invalid_request_error", "Messages must be a non-empty array."
        )
    messages: list[Message] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise OpenAIAdapterError(
                "invalid_request_error", "Each message must be an object."
            )
        try:
            role = MessageRole(str(item.get("role") or ""))
        except ValueError as exc:
            raise OpenAIAdapterError(
                "unsupported_parameter", "Unsupported message role."
            ) from exc
        content = item.get("content")
        if not isinstance(content, str):
            raise OpenAIAdapterError(
                "unsupported_parameter", "Only text message content is supported."
            )
        if item.get("tool_calls") or item.get("tool_call_id"):
            raise OpenAIAdapterError(
                "unsupported_parameter",
                "Client-managed tool execution is not supported.",
            )
        messages.append(Message(role=role, text=content))
    return tuple(messages)


def _validated_generation_value(key: str, value: object) -> int | float:
    """Return one bounded provider-neutral generation control."""
    if key in {"max_tokens", "seed"}:
        if isinstance(value, bool) or not isinstance(value, int):
            raise OpenAIAdapterError("invalid_request_error", f"{key} must be an integer.")
        if key == "max_tokens" and not 1 <= value <= 32768:
            raise OpenAIAdapterError(
                "invalid_request_error", "max_tokens must be between 1 and 32768."
            )
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpenAIAdapterError("invalid_request_error", f"{key} must be numeric.")
    numeric = float(value)
    maximum = 2.0 if key == "temperature" else 1.0
    if not 0.0 <= numeric <= maximum:
        raise OpenAIAdapterError(
            "invalid_request_error", f"{key} must be between 0 and {maximum:g}."
        )
    return numeric


def _openai_error(error: ProcessingError) -> dict[str, Any]:
    """Map a safe canonical error to OpenAI's error shape."""
    return {
        "message": error.message,
        "type": "invalid_request_error" if not error.retryable else "server_error",
        "param": None,
        "code": error.code.lower(),
        "correlation_id": error.correlation_id,
    }


def _usage_payload(usage: Any) -> dict[str, int]:
    """Return OpenAI token accounting from canonical usage."""
    return {
        "prompt_tokens": int(usage.prompt_tokens),
        "completion_tokens": int(usage.completion_tokens),
        "total_tokens": int(usage.total_tokens),
    }


def _chat_chunk(
    *,
    completion_id: str,
    created: int,
    model: str | None,
    delta: Mapping[str, Any],
    finish_reason: str | None,
) -> dict[str, Any]:
    """Build one Chat Completions streaming chunk."""
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": dict(delta),
                "finish_reason": finish_reason,
            }
        ],
    }


def _sse_frame(value: Mapping[str, Any]) -> str:
    """Serialise one JSON object as a server-sent event data frame."""
    return f"data: {json.dumps(dict(value), ensure_ascii=False)}\n\n"
