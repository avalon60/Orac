"""Bounded probes for buffered and streamed structured-tool behaviour."""

# Author: Clive Bostock
# Date: 2026-08-31
# Description: Classifies exact-model tool probes and bounded transient retries.

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import time
from typing import Any, Callable, Iterable

from .protocol import ToolStreamEvent
from .protocol import ToolStreamEventKind
from .protocol import governed_retrieve_tool_schema


class ProbeOutcome(str, Enum):
    """Terminal classification for one bounded probe stage."""

    PASS = "PASS"
    MODEL_REJECTED = "MODEL_REJECTED"
    TRANSIENT_FAILURE = "TRANSIENT_FAILURE"
    NOT_RUN = "NOT_RUN"


@dataclass(frozen=True, slots=True)
class ToolProbeStageReport:
    """Content-free result for one buffered or streamed probe stage."""

    outcome: ProbeOutcome
    tool_call_count: int
    malformed_or_incomplete_calls: int
    provider_completed: bool
    visible_characters_before_tool: int
    reason_code: str
    attempts: int = 1


@dataclass(frozen=True, slots=True)
class ToolCapabilityProbeReport:
    """Combined structured and streamed evidence for one exact runtime."""

    structured: ToolProbeStageReport
    streamed: ToolProbeStageReport
    first_visible_to_tool_ms: int | None = None

    @property
    def structured_framing_valid(self) -> bool:
        """Return whether buffered structured behaviour was demonstrated."""
        return self.structured.outcome is ProbeOutcome.PASS

    @property
    def streamed_framing_valid(self) -> bool:
        """Return whether streamed structured behaviour was demonstrated."""
        return self.streamed.outcome is ProbeOutcome.PASS

    @property
    def tool_call_count(self) -> int:
        """Return the streamed count when run, otherwise the buffered count."""
        if self.streamed.outcome is not ProbeOutcome.NOT_RUN:
            return self.streamed.tool_call_count
        return self.structured.tool_call_count

    @property
    def malformed_or_incomplete_calls(self) -> int:
        """Return the aggregate malformed call count."""
        return (
            self.structured.malformed_or_incomplete_calls
            + self.streamed.malformed_or_incomplete_calls
        )

    @property
    def visible_characters_before_tool(self) -> int:
        """Return the maximum visible pre-tool output across both stages."""
        return max(
            self.structured.visible_characters_before_tool,
            self.streamed.visible_characters_before_tool,
        )

    @property
    def provider_completed(self) -> bool:
        """Return whether every executed stage completed at the provider."""
        reports = [self.structured]
        if self.streamed.outcome is not ProbeOutcome.NOT_RUN:
            reports.append(self.streamed)
        return all(item.provider_completed for item in reports)

    @property
    def reason_code(self) -> str:
        """Return one compatibility reason code for command-line reporting."""
        if self.structured.outcome is not ProbeOutcome.PASS:
            return self.structured.reason_code
        if self.streamed.outcome is not ProbeOutcome.PASS:
            return self.streamed.reason_code
        return "PROBE_VERIFIED"


class StructuredToolCapabilityProbe:
    """Probe buffered and streamed tool behaviour without executing retrieval."""

    RETRY_DELAYS_SECONDS = (10.0, 30.0)
    MAX_ATTEMPTS = 3

    def run(self, connector: Any) -> ToolCapabilityProbeReport:
        """Run each fixed probe stage once."""
        return self.run_with_retries(connector, sleep=lambda _: None, max_attempts=1)

    def run_with_retries(
        self,
        connector: Any,
        *,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> ToolCapabilityProbeReport:
        """Run deterministic bounded retries for transient stage failures."""
        if not 1 <= max_attempts <= self.MAX_ATTEMPTS:
            raise ValueError("probe max_attempts must be between 1 and 3")
        messages, schema = self._fixture()
        structured = self._run_stage_with_retries(
            lambda: connector.buffered_tool_events(
                messages=messages,
                tools=[schema],
                generation_options={"temperature": 0.0, "num_predict": 128},
            ),
            stage="STRUCTURED",
            sleep=sleep,
            max_attempts=max_attempts,
        )
        if structured.outcome is not ProbeOutcome.PASS:
            return ToolCapabilityProbeReport(
                structured=structured,
                streamed=self._not_run("STREAMED_PROBE_SKIPPED"),
            )
        streamed = self._run_stage_with_retries(
            lambda: connector.stream_tool_events(
                messages=messages,
                tools=[schema],
                generation_options={"temperature": 0.0, "num_predict": 128},
            ),
            stage="STREAMED",
            sleep=sleep,
            max_attempts=max_attempts,
        )
        return ToolCapabilityProbeReport(
            structured=structured,
            streamed=streamed,
        )

    def _run_stage_with_retries(
        self,
        event_factory: Callable[[], Iterable[ToolStreamEvent]],
        *,
        stage: str,
        sleep: Callable[[float], None],
        max_attempts: int,
    ) -> ToolProbeStageReport:
        """Retry only transient failures using the fixed delay schedule."""
        report = self._not_run(f"{stage}_PROBE_NOT_RUN")
        for attempt in range(1, max_attempts + 1):
            report = self._run_stage(event_factory, stage=stage, attempt=attempt)
            if report.outcome is not ProbeOutcome.TRANSIENT_FAILURE:
                return report
            if attempt < max_attempts:
                sleep(self.RETRY_DELAYS_SECONDS[attempt - 1])
        return ToolProbeStageReport(
            outcome=report.outcome,
            tool_call_count=report.tool_call_count,
            malformed_or_incomplete_calls=report.malformed_or_incomplete_calls,
            provider_completed=report.provider_completed,
            visible_characters_before_tool=report.visible_characters_before_tool,
            reason_code=f"{stage}_PROBE_TRANSIENT_RETRY_EXHAUSTED",
            attempts=max_attempts,
        )

    def _run_stage(
        self,
        event_factory: Callable[[], Iterable[ToolStreamEvent]],
        *,
        stage: str,
        attempt: int,
    ) -> ToolProbeStageReport:
        """Collect and validate one provider-completed tool decision."""
        calls: dict[int, dict[str, Any]] = {}
        completed: set[int] = set()
        provider_completed = False
        visible_characters = 0
        characters_before_tool = 0
        first_tool_seen = False
        try:
            for event in event_factory():
                if event.kind is ToolStreamEventKind.ASSISTANT_TEXT_DELTA:
                    visible_characters += len(str(event.text or ""))
                elif event.kind is ToolStreamEventKind.TOOL_CALL_START:
                    if not first_tool_seen:
                        characters_before_tool = visible_characters
                        first_tool_seen = True
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
                    return self._transient(
                        stage,
                        attempt,
                        calls,
                        completed,
                        characters_before_tool,
                    )
        except Exception:
            return self._transient(
                stage,
                attempt,
                calls,
                completed,
                characters_before_tool,
            )
        if not provider_completed:
            return self._transient(
                stage,
                attempt,
                calls,
                completed,
                characters_before_tool,
            )
        valid_calls, malformed = self._validate_calls(calls, completed)
        valid = (
            valid_calls == 1
            and len(calls) == 1
            and malformed == 0
            and characters_before_tool == 0
        )
        return ToolProbeStageReport(
            outcome=(ProbeOutcome.PASS if valid else ProbeOutcome.MODEL_REJECTED),
            tool_call_count=len(calls),
            malformed_or_incomplete_calls=malformed,
            provider_completed=True,
            visible_characters_before_tool=characters_before_tool,
            reason_code=(
                f"{stage}_PROBE_VERIFIED"
                if valid
                else f"{stage}_PROBE_MODEL_REJECTED"
            ),
            attempts=attempt,
        )

    @staticmethod
    def _validate_calls(
        calls: dict[int, dict[str, Any]],
        completed: set[int],
    ) -> tuple[int, int]:
        """Validate the exact fixed retrieve call and return counts."""
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
        return valid_calls, malformed

    @staticmethod
    def _transient(
        stage: str,
        attempt: int,
        calls: dict[int, dict[str, Any]],
        completed: set[int],
        characters_before_tool: int,
    ) -> ToolProbeStageReport:
        """Return a content-free transient provider/infrastructure failure."""
        return ToolProbeStageReport(
            outcome=ProbeOutcome.TRANSIENT_FAILURE,
            tool_call_count=len(calls),
            malformed_or_incomplete_calls=max(0, len(calls.keys() - completed)),
            provider_completed=False,
            visible_characters_before_tool=characters_before_tool,
            reason_code=f"{stage}_PROBE_TRANSIENT_FAILURE",
            attempts=attempt,
        )

    @staticmethod
    def _not_run(reason_code: str) -> ToolProbeStageReport:
        """Return the explicit not-run stage state."""
        return ToolProbeStageReport(
            outcome=ProbeOutcome.NOT_RUN,
            tool_call_count=0,
            malformed_or_incomplete_calls=0,
            provider_completed=False,
            visible_characters_before_tool=0,
            reason_code=reason_code,
            attempts=0,
        )

    @staticmethod
    def _fixture() -> tuple[list[dict[str, str]], dict[str, Any]]:
        """Return the fixed bounded probe messages and tool schema."""
        return (
            [
                {
                    "role": "system",
                    "content": (
                        "This is a structured-tool framing probe. Call the "
                        "advertised retrieve tool exactly once. Do not emit "
                        "explanatory text."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Retrieve the prior fixture decision from conversation "
                        "memory."
                    ),
                },
            ],
            governed_retrieve_tool_schema(("CONVERSATION",)),
        )
