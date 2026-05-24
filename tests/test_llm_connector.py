"""Deterministic tests for Ollama connector retry behaviour.

# Author: Clive Bostock
# Date: 2026-04-27
# Description: Verifies that Ollama completions retry with a larger
#   num_predict budget when done_reason indicates truncation.
"""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


if "langchain_openai" not in sys.modules:
    stub_module = types.ModuleType("langchain_openai")

    class _StubChatOpenAI:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def invoke(self, prompt):
            return prompt

    stub_module.ChatOpenAI = _StubChatOpenAI
    sys.modules["langchain_openai"] = stub_module


from model.llm_connector import (
    OllamaConnector,
    normalise_generation_options,
    provider_generation_options,
)


class _FakeLogger:
    """Capture connector log messages for assertions."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def log_info(self, message: str) -> None:
        self.messages.append(message)


class _StubOllamaConnector(OllamaConnector):
    """Small Ollama connector stub for deterministic retry tests."""

    def __init__(
        self,
        *,
        chat_results: list[dict[str, str]],
        default_num_predict: int = 2048,
        num_predict_incr_pct: int = 100,
        max_num_predict_retries: int = 2,
    ) -> None:
        self.logger = _FakeLogger()
        self.system_hint = "You are Orac."
        self.default_num_predict = default_num_predict
        self.num_predict_incr_pct = num_predict_incr_pct
        self._max_num_predict_retries = max_num_predict_retries
        self._chat_results = list(chat_results)
        self._generate_results: list[dict[str, str]] = []
        self.chat_num_predicts: list[int] = []
        self.generate_num_predicts: list[int] = []

    def _chat_once(
        self,
        prompt: str,
        *,
        show_reasoning: bool,
        num_predict: int,
        use_system: bool,
        generation_options: dict | None = None,
    ) -> dict[str, str]:
        del prompt, show_reasoning, use_system, generation_options
        self.chat_num_predicts.append(num_predict)
        if self._chat_results:
            return self._chat_results.pop(0)
        return {"text": "", "done_reason": "stop"}

    def _generate_once(
        self,
        prompt: str,
        *,
        num_predict: int,
        generation_options: dict | None = None,
    ) -> dict[str, str]:
        del prompt, generation_options
        self.generate_num_predicts.append(num_predict)
        if self._generate_results:
            return self._generate_results.pop(0)
        return {"text": "", "done_reason": "stop"}


class OllamaConnectorRetryTests(unittest.TestCase):
    """Tests truncation-aware retry behaviour for Ollama completions."""

    def test_send_prompt_retries_with_higher_num_predict_after_length_stop(
        self,
    ) -> None:
        connector = _StubOllamaConnector(
            chat_results=[
                {"text": "partial answer", "done_reason": "length"},
                {"text": "completed answer", "done_reason": "stop"},
            ],
            default_num_predict=200,
            num_predict_incr_pct=50,
        )

        response = connector.send_prompt(
            prompt_type="U",
            prompt="Explain the battle.",
        )

        self.assertEqual(response, "completed answer")
        self.assertEqual(connector.chat_num_predicts, [200, 300])
        self.assertEqual(connector.generate_num_predicts, [])

    def test_send_prompt_returns_first_complete_response_without_retry(self) -> None:
        connector = _StubOllamaConnector(
            chat_results=[
                {"text": "complete answer", "done_reason": "stop"},
            ],
            default_num_predict=384,
            num_predict_incr_pct=100,
        )

        response = connector.send_prompt(
            prompt_type="U",
            prompt="What happened?",
        )

        self.assertEqual(response, "complete answer")
        self.assertEqual(connector.chat_num_predicts, [384])
        self.assertEqual(connector.generate_num_predicts, [])

    def test_generation_options_omit_internal_context_and_stop_fields(self) -> None:
        options = normalise_generation_options(
            {
                "temperature": 0.5,
                "num_ctx": 8192,
                "stop": ["</tool>"],
                "stop_sequences": ["</json>"],
            }
        )

        self.assertEqual(options, {"temperature": 0.5})

    def test_provider_generation_options_map_supported_fields_only(self) -> None:
        options = {
            "temperature": 0.4,
            "top_p": 0.9,
            "top_k": 40,
            "repeat_penalty": 1.1,
            "num_predict": 1024,
            "seed": 42,
        }

        self.assertEqual(
            provider_generation_options("ollama", options),
            {
                "temperature": 0.4,
                "top_p": 0.9,
                "top_k": 40,
                "repeat_penalty": 1.1,
                "num_predict": 1024,
                "seed": 42,
            },
        )
        self.assertEqual(
            provider_generation_options("lmstudio", options),
            {
                "temperature": 0.4,
                "top_p": 0.9,
                "max_tokens": 1024,
            },
        )

    def test_generation_option_num_predict_overrides_initial_retry_budget(self) -> None:
        connector = _StubOllamaConnector(
            chat_results=[
                {"text": "complete answer", "done_reason": "stop"},
            ],
            default_num_predict=200,
        )

        response = connector.send_prompt(
            prompt_type="U",
            prompt="What happened?",
            generation_options={"num_predict": 768},
        )

        self.assertEqual(response, "complete answer")
        self.assertEqual(connector.chat_num_predicts, [768])


if __name__ == "__main__":
    unittest.main()
