"""Provider-neutral structured-tool protocol for governed retrieval."""

# Author: Clive Bostock
# Date: 2026-08-29
# Description: Defines normalized incremental events and the exact retrieval schema.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

RETRIEVE_TOOL_NAME = "retrieve"
GOVERNED_RETRIEVAL_SYSTEM_INSTRUCTION = (
    "You have one advertised read-only retrieve tool for authorised prior "
    "evidence. If the user explicitly requests that tool, you MUST issue exactly "
    "one structured tool call before answering and MUST NOT emit explanatory text "
    "first. Never claim retrieval occurred, invent retrieval output, or simulate a "
    "tool result unless an actual tool result appears in the provider transcript. "
    "When retrieval is not needed and was not explicitly requested, answer normally "
    "without calling the tool. The host controls scope, authority, evidence bounds, "
    "and execution."
)


class ToolDecisionMode(StrEnum):
    """Effective structured-tool execution modes."""

    STREAMING = "STREAMING"
    BUFFERED = "BUFFERED"
    NONE = "NONE"


class ToolStreamEventKind(StrEnum):
    """Normalized provider events visible to the coordinator only."""

    ASSISTANT_TEXT_DELTA = "ASSISTANT_TEXT_DELTA"
    REASONING_DELTA = "REASONING_DELTA"
    TOOL_CALL_START = "TOOL_CALL_START"
    TOOL_CALL_ARGUMENT_DELTA = "TOOL_CALL_ARGUMENT_DELTA"
    TOOL_CALL_COMPLETED = "TOOL_CALL_COMPLETED"
    ASSISTANT_COMPLETION = "ASSISTANT_COMPLETION"
    USAGE = "USAGE"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class ToolStreamEvent:
    """One provider-neutral incremental model event."""

    kind: ToolStreamEventKind
    text: str = ""
    call_id: str = ""
    call_index: int = 0
    tool_name: str = ""
    arguments_delta: str = ""
    finish_reason: str = ""
    usage: Mapping[str, Any] | None = None
    error_code: str = ""


@dataclass(frozen=True, slots=True)
class StructuredToolCall:
    """One completely assembled structured tool call."""

    call_id: str
    name: str
    arguments_json: str


def governed_retrieve_tool_schema(
    allowed_domains: tuple[str, ...] = (),
    *,
    domain_handles: tuple[str, ...] | None = None,
    max_selected_domains: int = 1,
) -> dict[str, Any]:
    """Return the exact model-facing schema for host-governed retrieval."""
    if domain_handles is not None:
        handles = tuple(dict.fromkeys(str(item) for item in domain_handles))
        if not handles:
            raise ValueError("at least one governed domain handle is required")
        if max_selected_domains <= 0:
            raise ValueError("maximum selected domains must be positive")
        return {
            "type": "function",
            "function": {
                "name": RETRIEVE_TOOL_NAME,
                "description": (
                    "Search one or more advertised authorised knowledge domains. "
                    "Use only opaque handles from this invocation."
                ),
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["query", "domains"],
                    "properties": {
                        "query": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 2048,
                        },
                        "domains": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": min(max_selected_domains, len(handles)),
                            "uniqueItems": True,
                            "items": {"type": "string", "enum": list(handles)},
                        },
                    },
                },
            },
        }
    domains = tuple(dict.fromkeys(str(item).upper() for item in allowed_domains))
    if not domains:
        raise ValueError("at least one governed retrieval domain is required")
    return {
        "type": "function",
        "function": {
            "name": RETRIEVE_TOOL_NAME,
            "description": (
                "Search an authorised Orac knowledge domain when prior evidence "
                "is needed. The host determines all ownership and scope."
            ),
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "required": ["query", "domain"],
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 2048},
                    "domain": {"type": "string", "enum": list(domains)},
                },
            },
        },
    }
