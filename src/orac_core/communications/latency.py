"""Collect content-free high-resolution chat latency measurements."""

# Author: Clive Bostock
# Date: 04-Oct-2026
# Description: Records correlated phase timings for communications requests.

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
import json
import time
from typing import Any

_CURRENT_TRACE: ContextVar["ChatLatencyTrace | None"] = ContextVar(
    "orac_chat_latency_trace", default=None
)


@dataclass(slots=True)
class ChatLatencyTrace:
    """Record monotonic request milestones and safe diagnostic metadata."""

    request_id: str
    correlation_id: str
    enabled: bool = True
    started_at: float = field(default_factory=time.perf_counter)
    milestones: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def mark(self, phase: str) -> None:
        """Record the elapsed time at one named milestone."""
        if self.enabled:
            self.milestones[phase] = time.perf_counter() - self.started_at

    def set(self, **metadata: Any) -> None:
        """Add bounded content-free diagnostic metadata."""
        if not self.enabled:
            return
        for key, value in metadata.items():
            if value is not None and isinstance(value, (str, int, float, bool)):
                self.metadata[key] = value

    def elapsed_ms(self, phase: str) -> float | None:
        """Return a milestone's elapsed milliseconds."""
        value = self.milestones.get(phase)
        return round(value * 1000.0, 3) if value is not None else None

    def duration_ms(self, start: str, end: str) -> float | None:
        """Return milliseconds between two recorded milestones."""
        start_value = self.milestones.get(start)
        end_value = self.milestones.get(end)
        if start_value is None or end_value is None:
            return None
        return round(max(0.0, end_value - start_value) * 1000.0, 3)

    def summary(self) -> dict[str, Any]:
        """Return a structured, content-free request summary."""
        phases_ms = {
            phase: round(elapsed * 1000.0, 3)
            for phase, elapsed in sorted(self.milestones.items(), key=lambda item: item[1])
        }
        return {
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "phases_ms": phases_ms,
            "metadata": dict(self.metadata),
            "total_ms": round((time.perf_counter() - self.started_at) * 1000.0, 3),
        }

    def log_line(self) -> str:
        """Serialise the summary for one structured operational log entry."""
        return "chat latency: " + json.dumps(
            self.summary(), ensure_ascii=True, separators=(",", ":"), sort_keys=True
        )


def bind_latency_trace(trace: ChatLatencyTrace) -> Token[ChatLatencyTrace | None]:
    """Bind a trace to the current asynchronous request context."""
    return _CURRENT_TRACE.set(trace)


def reset_latency_trace(token: Token[ChatLatencyTrace | None]) -> None:
    """Restore the prior request trace binding."""
    _CURRENT_TRACE.reset(token)


def current_latency_trace() -> ChatLatencyTrace | None:
    """Return the trace bound to the current asynchronous request context."""
    return _CURRENT_TRACE.get()
