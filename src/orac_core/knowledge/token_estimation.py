"""Conservative token and byte accounting for knowledge materialisation."""

# Author: Clive Bostock
# Date: 14-Aug-2026
# Description: Estimates bounded evidence tokens before and after materialisation.

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True, slots=True)
class TokenEstimate:
    """One auditable content estimate without retaining the estimated content."""

    estimator_code: str
    estimator_version: str
    byte_count: int
    character_count: int | None
    base_token_count: int
    safety_margin_percent: int
    safe_token_count: int
    part_count: int
    verified: bool


class ConservativeUtf8TokenEstimator:
    """Estimate evidence tokens conservatively without a model tokenizer dependency."""

    CODE = "UTF8_CONSERVATIVE"
    VERSION = "1"

    def __init__(
        self,
        *,
        safety_margin_percent: int = 20,
        per_part_overhead_tokens: int = 32,
    ) -> None:
        """Initialise immutable estimator safety settings."""
        if not 0 <= int(safety_margin_percent) <= 100:
            raise ValueError("safety_margin_percent must be between 0 and 100")
        if int(per_part_overhead_tokens) < 0:
            raise ValueError("per_part_overhead_tokens must be non-negative")
        self._safety_margin_percent = int(safety_margin_percent)
        self._per_part_overhead_tokens = int(per_part_overhead_tokens)

    def estimate_registered_bytes(
        self,
        byte_count: int,
        *,
        part_count: int = 1,
    ) -> TokenEstimate:
        """Estimate from registered UTF-8 bytes before managed content is read."""
        bytes_value = _nonnegative_int(byte_count, "byte_count")
        parts_value = _positive_int(part_count, "part_count")
        base = math.ceil(bytes_value / 2) + (
            parts_value * self._per_part_overhead_tokens
        )
        return self._result(
            byte_count=bytes_value,
            character_count=None,
            base_token_count=base,
            part_count=parts_value,
            verified=False,
        )

    def estimate_text(
        self,
        text: str,
        *,
        media_type: str = "text/plain; charset=utf-8",
        part_count: int = 1,
    ) -> TokenEstimate:
        """Estimate verified UTF-8 text using representation-specific ratios."""
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        parts_value = _positive_int(part_count, "part_count")
        payload = text.encode("utf-8")
        media = str(media_type).strip().lower()
        if media.startswith("text/csv") or media == "application/json":
            content_tokens = max(math.ceil(len(text) / 2), math.ceil(len(payload) / 3))
        else:
            content_tokens = max(math.ceil(len(text) / 3), math.ceil(len(payload) / 4))
        base = content_tokens + (parts_value * self._per_part_overhead_tokens)
        return self._result(
            byte_count=len(payload),
            character_count=len(text),
            base_token_count=base,
            part_count=parts_value,
            verified=True,
        )

    def estimate_parts(
        self,
        parts: Iterable[tuple[bytes, str]],
    ) -> TokenEstimate:
        """Estimate already verified UTF-8 parts and aggregate their accounting."""
        byte_count = 0
        character_count = 0
        content_tokens = 0
        part_count = 0
        for payload, media_type in parts:
            if not isinstance(payload, bytes):
                raise TypeError("part payloads must be bytes")
            text = payload.decode("utf-8", errors="strict")
            estimate = self.estimate_text(
                text,
                media_type=media_type,
                part_count=1,
            )
            byte_count += estimate.byte_count
            character_count += estimate.character_count or 0
            content_tokens += estimate.base_token_count - self._per_part_overhead_tokens
            part_count += 1
        if part_count == 0:
            return self._result(
                byte_count=0,
                character_count=0,
                base_token_count=0,
                part_count=0,
                verified=True,
            )
        return self._result(
            byte_count=byte_count,
            character_count=character_count,
            base_token_count=(
                content_tokens + part_count * self._per_part_overhead_tokens
            ),
            part_count=part_count,
            verified=True,
        )

    def estimate_envelope(self, envelope_text: str) -> TokenEstimate:
        """Estimate the exact rendered canonical evidence envelope.

        Args:
            envelope_text (str): Complete outer markers and canonical JSON.

        Returns:
            TokenEstimate: Verified conservative accounting for the envelope.
        """
        return self.estimate_text(
            envelope_text,
            media_type="application/json",
            part_count=1,
        )

    def estimate_prompt(self, prompt: str) -> TokenEstimate:
        """Estimate the exact immutable flat-text prompt submitted to a model.

        Args:
            prompt (str): Fully assembled model input.

        Returns:
            TokenEstimate: Verified conservative accounting for the prompt.
        """
        return self.estimate_text(
            prompt,
            media_type="text/plain; charset=utf-8",
            part_count=1,
        )

    def _result(
        self,
        *,
        byte_count: int,
        character_count: int | None,
        base_token_count: int,
        part_count: int,
        verified: bool,
    ) -> TokenEstimate:
        """Build one immutable estimate with the configured safety margin."""
        safe_tokens = math.ceil(
            base_token_count * (100 + self._safety_margin_percent) / 100
        )
        return TokenEstimate(
            estimator_code=self.CODE,
            estimator_version=self.VERSION,
            byte_count=byte_count,
            character_count=character_count,
            base_token_count=base_token_count,
            safety_margin_percent=self._safety_margin_percent,
            safe_token_count=safe_tokens,
            part_count=part_count,
            verified=verified,
        )


def _nonnegative_int(value: int, field_name: str) -> int:
    """Return a non-negative integer without accepting booleans."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _positive_int(value: int, field_name: str) -> int:
    """Return a positive integer without accepting booleans."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value
