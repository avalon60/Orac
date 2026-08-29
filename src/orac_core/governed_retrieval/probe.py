"""Bounded content-free probes for streamed structured-tool framing."""
# Author: Clive Bostock
# Date: 2026-08-29
# Description: Measures adapter framing for administrative capability review.

from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any

from .protocol import ToolStreamEventKind
from .protocol import governed_retrieve_tool_schema


@dataclass(frozen=True, slots=True)
class ToolCapabilityProbeReport:
    """Content-free bounded evidence produced by one exact runtime probe."""

    structured_framing_valid: bool
    streamed_framing_valid: bool
    tool_call_count: int
    malformed_or_incomplete_calls: int
    first_visible_to_tool_ms: int | None
    visible_characters_before_tool: int
    provider_completed: bool
    reason_code: str


class StructuredToolCapabilityProbe:
    """Probe connector framing without executing retrieval or mutating evidence."""

    def run(self, connector: Any) -> ToolCapabilityProbeReport:
        """Run one deterministic fixture with a small output allowance."""
        schema = governed_retrieve_tool_schema(("CONVERSATION",))
        messages = [
            {
                "role": "system",
                "content": (
                    "This is a structured-tool framing probe. Call the advertised "
                    "retrieve tool exactly once. Do not emit explanatory text."
                ),
            },
            {
                "role": "user",
                "content": "Retrieve the prior fixture decision from conversation memory.",
            },
        ]
        started = time.monotonic()
        first_visible_at: float | None = None
        visible_characters = 0
        characters_before_tool = 0
        first_tool_at: float | None = None
        calls: dict[int, dict[str, Any]] = {}
        completed: set[int] = set()
        provider_completed = False
        try:
            events = connector.stream_tool_events(
                messages=messages,
                tools=[schema],
                generation_options={"temperature": 0.0, "num_predict": 128},
            )
            for event in events:
                if event.kind is ToolStreamEventKind.ASSISTANT_TEXT_DELTA:
                    if first_visible_at is None:
                        first_visible_at = time.monotonic()
                    visible_characters += len(str(event.text or ""))
                elif event.kind is ToolStreamEventKind.TOOL_CALL_START:
                    if first_tool_at is None:
                        first_tool_at = time.monotonic()
                        characters_before_tool = visible_characters
                    calls.setdefault(
                        event.call_index,
                        {"name": event.tool_name, "arguments": []},
                    )
                elif event.kind is ToolStreamEventKind.TOOL_CALL_ARGUMENT_DELTA:
                    calls.setdefault(
                        event.call_index,
                        {"name": event.tool_name, "arguments": []},
                    )["arguments"].append(str(event.arguments_delta or ""))
                elif event.kind is ToolStreamEventKind.TOOL_CALL_COMPLETED:
                    completed.add(event.call_index)
                elif event.kind is ToolStreamEventKind.ASSISTANT_COMPLETION:
                    provider_completed = True
                elif event.kind is ToolStreamEventKind.ERROR:
                    return self._failure(
                        reason_code=event.error_code or "PROBE_PROVIDER_ERROR",
                        calls=calls,
                        completed=completed,
                        provider_completed=provider_completed,
                        first_visible_at=first_visible_at,
                        first_tool_at=first_tool_at,
                        started=started,
                        characters_before_tool=characters_before_tool,
                    )
        except Exception:
            return self._failure(
                reason_code="PROBE_PROVIDER_ERROR",
                calls=calls,
                completed=completed,
                provider_completed=provider_completed,
                first_visible_at=first_visible_at,
                first_tool_at=first_tool_at,
                started=started,
                characters_before_tool=characters_before_tool,
            )

        valid_calls = 0
        malformed = 0
        for index, call in calls.items():
            try:
                arguments = json.loads("".join(call["arguments"]))
            except (TypeError, ValueError, json.JSONDecodeError):
                malformed += 1
                continue
            if (
                index in completed
                and call["name"] == "retrieve"
                and isinstance(arguments, dict)
                and set(arguments) == {"query", "domain"}
                and isinstance(arguments["query"], str)
                and bool(arguments["query"].strip())
                and arguments["domain"] == "CONVERSATION"
            ):
                valid_calls += 1
            else:
                malformed += 1
        malformed += len(completed - calls.keys()) + len(calls.keys() - completed)
        valid = valid_calls == 1 and len(calls) == 1 and malformed == 0
        return ToolCapabilityProbeReport(
            structured_framing_valid=valid,
            streamed_framing_valid=valid and provider_completed,
            tool_call_count=len(calls),
            malformed_or_incomplete_calls=malformed,
            first_visible_to_tool_ms=self._timing_ms(
                first_visible_at, first_tool_at, started
            ),
            visible_characters_before_tool=characters_before_tool,
            provider_completed=provider_completed,
            reason_code=("PROBE_VERIFIED" if valid else "PROBE_FRAMING_INVALID"),
        )

    @classmethod
    def _failure(
        cls,
        *,
        reason_code: str,
        calls: dict[int, dict[str, Any]],
        completed: set[int],
        provider_completed: bool,
        first_visible_at: float | None,
        first_tool_at: float | None,
        started: float,
        characters_before_tool: int,
    ) -> ToolCapabilityProbeReport:
        """Return a content-free failure report."""
        return ToolCapabilityProbeReport(
            structured_framing_valid=False,
            streamed_framing_valid=False,
            tool_call_count=len(calls),
            malformed_or_incomplete_calls=max(1, len(calls.keys() - completed)),
            first_visible_to_tool_ms=cls._timing_ms(
                first_visible_at, first_tool_at, started
            ),
            visible_characters_before_tool=characters_before_tool,
            provider_completed=provider_completed,
            reason_code=str(reason_code)[:100],
        )

    @staticmethod
    def _timing_ms(
        first_visible_at: float | None,
        first_tool_at: float | None,
        started: float,
    ) -> int | None:
        """Return safe timing only when both visible output and a tool call exist."""
        del started
        if first_tool_at is None or first_visible_at is None:
            return None
        return max(0, int((first_tool_at - first_visible_at) * 1000))
