"""Expose transport adapters for canonical Orac communications."""

# Author: Clive Bostock
# Date: 2026-09-20
# Description: Groups reusable transport conversion helpers.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from orac_core.communications.adapters.openai import OpenAIAdapter
from orac_core.communications.adapters.voice import VoiceAdapter

__all__ = ["OpenAIAdapter", "VoiceAdapter"]
