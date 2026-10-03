"""Adapt authenticated voice protocol frames to canonical Orac requests."""

# Author: Clive Bostock
# Date: 2026-09-25
# Description: Keeps voice identity and transport concerns outside orchestration.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from orac_core.communications.adapters.ndjson import authenticated_frame_to_request
from orac_core.communications.models import OracRequest
from orac_core.communications.models import PrincipalContext


class VoiceAdapterError(ValueError):
    """Raised when an authenticated frame is not a voice request."""


class VoiceAdapter:
    """Construct canonical requests for the existing voice transport."""

    def to_request(
        self,
        frame: Mapping[str, Any],
        *,
        principal: PrincipalContext,
    ) -> OracRequest:
        """Convert one authenticated voice frame to canonical form.

        Args:
            frame: Validated v1 request frame received from the voice client.
            principal: Identity established by the host frame-auth boundary.

        Returns:
            The canonical request consumed by ``OracRequestProcessor``.

        Raises:
            VoiceAdapterError: If the frame is not voice-originated.
        """
        metadata = frame.get("meta")
        metadata = metadata if isinstance(metadata, Mapping) else {}
        if str(metadata.get("channel") or "").strip().lower() != "voice":
            raise VoiceAdapterError("A voice channel frame is required.")
        request = authenticated_frame_to_request(frame, principal=principal)
        return replace(request, source="voice")
