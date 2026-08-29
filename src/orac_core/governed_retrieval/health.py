"""Phase 2A-local operational health for streamed tool calling."""
# Author: Clive Bostock
# Date: 2026-08-29
# Description: Temporarily suppresses unhealthy streaming without mutating evidence.

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
import time
from typing import Callable


class StreamingHealthState(StrEnum):
    """Current operational state for one concrete provider/runtime/model tuple."""

    HEALTHY = "HEALTHY"
    SUPPRESSED = "SUPPRESSED"
    HALF_OPEN = "HALF_OPEN"


@dataclass(frozen=True, slots=True)
class StreamingHealthKey:
    """Non-secret identity for one validated streamed-tool combination."""

    provider_id: str
    runtime_fingerprint: str
    adapter_revision: str
    llm_id: int
    model_revision: str


@dataclass(slots=True)
class _HealthRecord:
    observations: deque[tuple[float, bool, str]] = field(default_factory=deque)
    consecutive_unhealthy: int = 0
    suppressed_until: float = 0.0
    cooldown_seconds: float = 300.0
    half_open_claimed: bool = False
    half_open_claimed_at: float = 0.0
    reason_code: str = ""


class StreamingToolHealthTracker:
    """Bounded in-memory circuit breaker for streamed tool framing health."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        observation_window_seconds: float = 900.0,
        maximum_observations: int = 50,
        unhealthy_ratio: float = 0.30,
        minimum_ratio_samples: int = 10,
        consecutive_unhealthy_limit: int = 3,
        initial_cooldown_seconds: float = 300.0,
        maximum_cooldown_seconds: float = 1800.0,
    ) -> None:
        """Initialise deterministic suppression thresholds."""
        self._clock = clock
        self._window = observation_window_seconds
        self._maximum_observations = maximum_observations
        self._unhealthy_ratio = unhealthy_ratio
        self._minimum_ratio_samples = minimum_ratio_samples
        self._consecutive_limit = consecutive_unhealthy_limit
        self._initial_cooldown = initial_cooldown_seconds
        self._maximum_cooldown = maximum_cooldown_seconds
        self._records: dict[StreamingHealthKey, _HealthRecord] = {}

    def state(self, key: StreamingHealthKey) -> tuple[StreamingHealthState, str]:
        """Return current health without changing capability evidence."""
        record = self._records.setdefault(
            key, _HealthRecord(cooldown_seconds=self._initial_cooldown)
        )
        now = self._clock()
        self._prune(record, now)
        if record.suppressed_until > now:
            return StreamingHealthState.SUPPRESSED, record.reason_code
        if record.suppressed_until:
            if record.half_open_claimed:
                if now - record.half_open_claimed_at < self._initial_cooldown:
                    return StreamingHealthState.SUPPRESSED, "STREAM_HEALTH_HALF_OPEN_BUSY"
                record.half_open_claimed = False
            record.half_open_claimed = True
            record.half_open_claimed_at = now
            return StreamingHealthState.HALF_OPEN, "STREAM_HEALTH_RECOVERY_PROBE"
        return StreamingHealthState.HEALTHY, "STREAM_HEALTH_ACCEPTABLE"

    def record(
        self,
        key: StreamingHealthKey,
        *,
        healthy: bool,
        reason_code: str,
    ) -> StreamingHealthState:
        """Record a content-free observation and update temporary suppression."""
        record = self._records.setdefault(
            key, _HealthRecord(cooldown_seconds=self._initial_cooldown)
        )
        now = self._clock()
        self._prune(record, now)
        record.observations.append((now, healthy, str(reason_code)[:100]))
        while len(record.observations) > self._maximum_observations:
            record.observations.popleft()

        if healthy:
            record.consecutive_unhealthy = 0
            if record.half_open_claimed:
                record.suppressed_until = 0.0
                record.half_open_claimed = False
                record.half_open_claimed_at = 0.0
                record.cooldown_seconds = self._initial_cooldown
                record.reason_code = ""
            return StreamingHealthState.HEALTHY

        record.consecutive_unhealthy += 1
        unhealthy_count = sum(1 for _, ok, _ in record.observations if not ok)
        ratio_bad = (
            len(record.observations) >= self._minimum_ratio_samples
            and unhealthy_count / len(record.observations) >= self._unhealthy_ratio
        )
        if record.half_open_claimed or record.consecutive_unhealthy >= self._consecutive_limit or ratio_bad:
            if record.half_open_claimed:
                record.cooldown_seconds = min(
                    self._maximum_cooldown, record.cooldown_seconds * 2
                )
            record.suppressed_until = now + record.cooldown_seconds
            record.half_open_claimed = False
            record.half_open_claimed_at = 0.0
            record.reason_code = str(reason_code)[:100] or "STREAM_HEALTH_UNHEALTHY"
            return StreamingHealthState.SUPPRESSED
        return StreamingHealthState.HEALTHY

    def _prune(self, record: _HealthRecord, now: float) -> None:
        """Discard observations outside the bounded rolling window."""
        threshold = now - self._window
        while record.observations and record.observations[0][0] < threshold:
            record.observations.popleft()
