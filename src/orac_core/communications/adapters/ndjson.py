"""Convert authenticated legacy NDJSON frames to canonical Orac contracts."""

# Author: Clive Bostock
# Date: 2026-09-20
# Description: Preserves the v1 socket protocol at the communications boundary.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from orac_core.communications.models import ConversationContext
from orac_core.communications.models import Message
from orac_core.communications.models import MessageRole
from orac_core.communications.models import OracRequest
from orac_core.communications.models import OracResponse
from orac_core.communications.models import PrincipalContext
from orac_core.communications.models import StreamEvent
from orac_core.communications.models import bounded_metadata


class NdjsonAdapterError(ValueError):
    """Raised when an authenticated legacy frame cannot be converted."""


def authenticated_frame_to_request(
    frame: Mapping[str, Any],
    *,
    principal: PrincipalContext,
) -> OracRequest:
    """Convert a validated frame using identity supplied by frame auth."""
    if frame.get("type") != "request" or frame.get("route") != "orac.prompt":
        raise NdjsonAdapterError("Unsupported request type or route.")
    payload = frame.get("payload")
    payload = payload if isinstance(payload, Mapping) else {}
    wire_messages = payload.get("messages")
    if not isinstance(wire_messages, list):
        raise NdjsonAdapterError("Request messages must be a list.")
    messages = tuple(_message_from_wire(value) for value in wire_messages)
    current = next(
        (message for message in reversed(messages) if message.role is MessageRole.USER),
        None,
    )
    if current is None:
        raise NdjsonAdapterError("A user message is required.")
    history = messages[: messages.index(current)]
    metadata = frame.get("meta")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    request_id = str(frame.get("id") or "").strip()
    correlation_id = str(metadata.get("correlation_id") or request_id).strip()
    session_id = str(metadata.get("session_id") or "").strip() or None
    return OracRequest(
        request_id=request_id,
        correlation_id=correlation_id,
        principal=principal,
        conversation=ConversationContext(session_id=session_id, history=history),
        message=current,
        source=str(metadata.get("channel") or metadata.get("client") or "ndjson"),
        stream=bool(metadata.get("stream")),
        model=str(metadata.get("model") or "").strip() or None,
        metadata=bounded_metadata(metadata),
    )


def response_to_frame(response: OracResponse) -> dict[str, Any]:
    """Convert a canonical response to the legacy response envelope."""
    error = None
    if response.error is not None:
        error = {
            "code": response.error.code,
            "message": response.error.message,
        }
    usage = response.usage
    return {
        "v": 1,
        "type": "response",
        "id": f"res-{response.request_id}",
        "reply_to": response.request_id,
        "route": "orac.prompt",
        "meta": {
            **dict(response.metadata),
            "status": "error" if error else "ok",
            "model": response.model,
            "req_id": response.request_id,
            "correlation_id": response.correlation_id,
            "conversation_id": response.conversation_id,
            "provenance": dict(response.provenance),
        },
        "payload": (
            None
            if response.message is None
            else {
                "content": response.message.text,
                "usage": (
                    None
                    if usage is None
                    else {
                        "prompt_tokens": usage.prompt_tokens,
                        "completion_tokens": usage.completion_tokens,
                        "total_tokens": usage.total_tokens,
                    }
                ),
                "stop_reason": response.finish_reason,
            }
        ),
        "error": error,
    }


def event_to_frame(event: StreamEvent) -> dict[str, Any]:
    """Convert a canonical event to a legacy stream envelope."""
    payload: dict[str, Any] = {**event.data, "sequence": event.sequence}
    if event.delta is not None:
        payload["delta"] = event.delta
    if event.status is not None:
        payload["status"] = event.status
    event_type = {
        "start": "stream_start",
        "complete": "stream_end",
    }.get(event.kind.value, event.kind.value)
    if event.kind.value == "status" and event.status:
        event_type = event.status
    return {
        "v": 1,
        "type": event_type,
        "id": f"evt-{event.request_id}-{event.sequence}",
        "reply_to": event.request_id,
        "route": "orac.prompt",
        "meta": {
            **dict(event.metadata),
            "status": "error" if event.error else "ok",
            "req_id": event.request_id,
            "correlation_id": event.correlation_id,
        },
        "payload": payload,
        "error": (
            None
            if event.error is None
            else {"code": event.error.code, "message": event.error.message}
        ),
    }


def dumps_frame(frame: Mapping[str, Any]) -> str:
    """Serialise one NDJSON frame without appending a line separator."""
    return json.dumps(dict(frame), ensure_ascii=False)


def _message_from_wire(value: object) -> Message:
    """Convert one legacy message and reject unknown persisted roles."""
    if not isinstance(value, Mapping):
        raise NdjsonAdapterError("Each request message must be an object.")
    try:
        role = MessageRole(str(value.get("role") or ""))
    except ValueError as exc:
        raise NdjsonAdapterError("Unsupported message role.") from exc
    content = value.get("content")
    if not isinstance(content, str):
        raise NdjsonAdapterError("Message content must be text.")
    return Message(role=role, text=content)
