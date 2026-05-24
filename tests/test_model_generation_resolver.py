"""Tests for Orac model generation option resolution.

# Author: Clive Bostock
# Date: 2026-05-23
# Description: Verifies model preset precedence before provider request mapping.
"""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


if "langchain_openai" not in sys.modules:
    stub_module = types.ModuleType("langchain_openai")

    class _StubChatOpenAI:
        """Small import stub for controller import isolation."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.args = args
            self.kwargs = kwargs

        def invoke(self, prompt: str) -> str:
            """Return the supplied prompt unchanged."""
            return prompt

    stub_module.ChatOpenAI = _StubChatOpenAI
    sys.modules["langchain_openai"] = stub_module


from controller.orac import Orac


class _PresetContext:
    """Minimal context stub exposing model generation preset lookup."""

    def __init__(self) -> None:
        self.presets = {
            1: {
                "MODEL_PRESET_ID": 1,
                "MODEL_PRESET_CODE": "CREATIVE",
                "TEMPERATURE": 0.75,
                "NUM_PREDICT": 2048,
            },
            2: {
                "MODEL_PRESET_ID": 2,
                "MODEL_PRESET_CODE": "PRECISE",
                "TEMPERATURE": 0.1,
                "TOP_P": 0.9,
                "NUM_PREDICT": 1536,
            },
        }

    def get_model_generation_preset(
        self,
        *,
        model_preset_id: int | str | None = None,
        model_preset_code: str | None = None,
    ) -> dict[str, Any]:
        """Return a configured preset by id or code."""
        if model_preset_id not in (None, ""):
            return self.presets.get(int(model_preset_id), {})
        code = str(model_preset_code or "").strip().upper()
        for preset in self.presets.values():
            if preset["MODEL_PRESET_CODE"] == code:
                return preset
        return {}


class ModelGenerationResolverTests(unittest.TestCase):
    """Tests for provider-neutral generation option resolution."""

    def _orac(self) -> Orac:
        orchestrator = Orac.__new__(Orac)
        orchestrator.ctx = _PresetContext()
        return orchestrator

    def test_default_generation_options_are_used_without_preset(self) -> None:
        options = self._orac()._resolve_generation_options(
            meta={},
            provider="ollama",
        )

        self.assertEqual(
            options,
            {
                "temperature": 0.2,
                "repeat_penalty": 1.1,
            },
        )

    def test_persona_preset_overrides_selected_default_preset(self) -> None:
        options = self._orac()._resolve_generation_options(
            meta={
                "model_preset_id": 1,
                "orac_personality": {
                    "PERSONALITY_CODE": "DEFAULT",
                    "MODEL_PRESET_ID": 2,
                },
            },
            provider="ollama",
        )

        self.assertEqual(
            options,
            {
                "temperature": 0.1,
                "repeat_penalty": 1.1,
                "num_predict": 1536,
                "top_p": 0.9,
            },
        )


if __name__ == "__main__":
    unittest.main()
