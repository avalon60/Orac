"""Define transport-neutral contracts for Orac request processing."""

# Author: Clive Bostock
# Date: 2026-09-20
# Description: Defines immutable communications requests, responses, and events.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from orac_core.knowledge import KnowledgeScope

_EXTERNAL_METADATA_KEYS = frozenset(
    {
        "channel",
        "client",
        "client_trace",
        "date_format",
        "force_concise",
        "force_new_conversation",
        "max_tokens",
        "seed",
        "temperature",
        "top_p",
        "reply_language",
        "requested_context_tokens",
        "requested_keep_alive",
        "retrieval_response_style",
        "show_reasoning",
        "strip_reasoning_tags",
        "timezone",
        "trace_id",
        "tts_pitch",
        "tts_rate",
        "tts_voice_key",
        "user_location",
        "voice_session_id",
    }
)


class MessageRole(str, Enum):
    """Model-facing actors supported by the host context contract."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class StreamEventKind(str, Enum):
    """Kinds of transport-neutral processing events."""

    START = "start"
    TEXT_DELTA = "text_delta"
    RETRIEVAL_PROGRESS = "retrieval_progress"
    STATUS = "status"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class PrincipalContext:
    """Authenticated identity supplied by a trusted host integration."""

    username: str
    roles: tuple[str, ...] = ()
    host_identity: str | None = None


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Describe one structured call to a host-authorised capability."""

    call_id: str
    capability_id: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Describe a bounded result returned by a host capability."""

    call_id: str
    capability_id: str
    status: str
    content: str = ""
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Message:
    """Represent one canonical conversation message."""

    role: MessageRole
    text: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_result: ToolResult | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ConversationContext:
    """Separate a host session reference from request-local history."""

    session_id: str | None = None
    conversation_id: str | None = None
    history: tuple[Message, ...] = ()


@dataclass(frozen=True, slots=True)
class CapabilityRestrictions:
    """Host-derived bounds that may narrow, but never grant, authority."""

    capability_ids: frozenset[str] | None = None
    knowledge_scopes: tuple[KnowledgeScope, ...] | None = None
    allow_web: bool | None = None
    model_ids: frozenset[str] | None = None


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Describe a capability without exposing a callable or import path."""

    capability_id: str
    name: str
    description: str
    parameters: Mapping[str, Any]
    plugin_id: str | None = None


@dataclass(frozen=True, slots=True)
class OracRequest:
    """Represent one validated request independent of its wire transport."""

    request_id: str
    correlation_id: str
    principal: PrincipalContext
    conversation: ConversationContext
    message: Message
    source: str
    stream: bool = False
    model: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    selected_capability_id: str | None = None
    restrictions: CapabilityRestrictions = field(default_factory=CapabilityRestrictions)
    tools: tuple[ToolDefinition, ...] = ()


@dataclass(frozen=True, slots=True)
class ProcessingError:
    """Expose a safe processing failure without its internal exception."""

    code: str
    message: str
    retryable: bool
    correlation_id: str


@dataclass(frozen=True, slots=True)
class Usage:
    """Record actual token usage when supplied by the selected model."""

    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        """Return total tokens reported for the request."""
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True, slots=True)
class OracResponse:
    """Represent the canonical outcome of one Orac request."""

    request_id: str
    correlation_id: str
    conversation_id: str | None
    model: str | None
    message: Message | None
    finish_reason: str
    usage: Usage | None = None
    provenance: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    error: ProcessingError | None = None


@dataclass(frozen=True, slots=True)
class StreamEvent:
    """Represent one ordered event emitted by the processing engine."""

    request_id: str
    correlation_id: str
    sequence: int
    kind: StreamEventKind
    delta: str | None = None
    status: str | None = None
    data: Mapping[str, Any] = field(default_factory=dict)
    result: OracResponse | None = None
    error: ProcessingError | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


def bounded_metadata(
    values: Mapping[str, Any] | None,
    *,
    maximum_items: int = 32,
) -> Mapping[str, Any]:
    """Return an immutable allowlisted projection of external metadata.

    Wire metadata is untrusted. Only correlation and presentation-neutral
    source labels cross into the canonical request; authentication,
    confirmation, model selection, history, routing flags, and authority are
    represented by dedicated host-owned fields instead.
    """
    if not values:
        return MappingProxyType({})
    selected: dict[str, Any] = {}
    for key, value in values.items():
        normalised_key = str(key).strip()
        allowlist_key = normalised_key.lower().replace("-", "_").replace(" ", "_")
        if not normalised_key or allowlist_key not in _EXTERNAL_METADATA_KEYS:
            continue
        if isinstance(value, str):
            bounded_value: Any = value[:256]
        elif isinstance(value, (bool, int, float)) or value is None:
            bounded_value = value
        else:
            continue
        selected[allowlist_key] = bounded_value
        if len(selected) >= maximum_items:
            break
    return MappingProxyType(selected)
