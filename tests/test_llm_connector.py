"""Deterministic tests for Ollama connector retry behaviour.

# Author: Clive Bostock
# Date: 2026-04-27
# Description: Verifies that Ollama completions retry with a larger
#   num_predict budget when done_reason indicates truncation.
"""

from __future__ import annotations

import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


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
    LLMConnector,
    LMStudioConnector,
    LLMUsageMetadata,
    OllamaConnector,
    normalise_generation_options,
    provider_generation_options,
)
from model.provider_registry import ProviderRegistry


class _FakeLogger:
    """Capture connector log messages for assertions."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def log_info(self, message: str) -> None:
        self.messages.append(message)

    def log_warning(self, message: str) -> None:
        self.messages.append(message)

    def log_error(self, message: str) -> None:
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


class _FallbackStreamingConnector(LLMConnector):
    """Connector that relies on the base non-streaming fallback contract."""

    def __init__(self, result: dict) -> None:
        self.model_interface_id = "lmstudio"
        self.llm_service_id = "lmstudio"
        self.result = result
        self.calls: list[tuple[str, str, bool, dict | None]] = []

    def list_models(self):
        """Return no models for the test double."""
        return []

    def send_prompt(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
        generation_options: dict | None = None,
    ) -> str:
        self.calls.append((prompt_type, prompt, stream, generation_options))
        return str(self.result.get("text") or "")

    def send_prompt_with_meta(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
        generation_options: dict | None = None,
    ) -> dict:
        self.calls.append((prompt_type, prompt, stream, generation_options))
        return self.result


class _FakeStreamResponse:
    """Context-manager response double for Ollama streaming tests."""

    def __init__(self, frames: list[dict]) -> None:
        self._frames = frames

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback

    def raise_for_status(self) -> None:
        """Pretend the HTTP response succeeded."""

    def iter_lines(self, decode_unicode: bool = False):
        """Yield encoded or decoded JSON stream lines."""
        for frame in self._frames:
            line = json.dumps(frame)
            yield line if decode_unicode else line.encode("utf-8")


class OllamaConnectorRetryTests(unittest.TestCase):
    """Tests truncation-aware retry behaviour for Ollama completions."""

    def test_provider_registry_resolves_known_providers(self) -> None:
        registry = ProviderRegistry()

        self.assertEqual(registry.connector_class("ollama"), OllamaConnector)
        self.assertEqual(registry.connector_class("lmstudio"), LMStudioConnector)
        self.assertEqual(registry.provider_ids(), ("lmstudio", "ollama"))

    def test_provider_registry_rejects_unknown_provider(self) -> None:
        registry = ProviderRegistry()

        with self.assertRaisesRegex(ValueError, "Unsupported LLM provider"):
            registry.connector_class("unknown")

        with self.assertRaisesRegex(ValueError, "Unsupported LLM provider"):
            registry.capabilities("unknown")

    def test_ollama_capabilities_are_explicit(self) -> None:
        capabilities = ProviderRegistry().capabilities("ollama")

        self.assertTrue(capabilities.supports_native_streaming)
        self.assertFalse(capabilities.uses_fallback_streaming)
        self.assertTrue(capabilities.supports_usage_metadata)
        self.assertTrue(capabilities.supports_model_listing)
        self.assertTrue(capabilities.supports_model_details)
        self.assertTrue(capabilities.supports_model_pull)
        self.assertFalse(capabilities.requires_loaded_model)

    def test_lmstudio_capabilities_are_explicit(self) -> None:
        capabilities = ProviderRegistry().capabilities("lmstudio")

        self.assertFalse(capabilities.supports_native_streaming)
        self.assertTrue(capabilities.uses_fallback_streaming)
        self.assertTrue(capabilities.supports_usage_metadata)
        self.assertTrue(capabilities.supports_model_listing)
        self.assertFalse(capabilities.supports_model_details)
        self.assertFalse(capabilities.supports_model_pull)
        self.assertTrue(capabilities.requires_loaded_model)

    def test_registry_owns_ollama_latest_alias_candidates(self) -> None:
        registry = ProviderRegistry()

        self.assertEqual(
            registry.model_lookup_candidates(
                provider_id="ollama",
                model_name="llama3.2",
            ),
            ["llama3.2", "llama3.2:latest"],
        )
        self.assertEqual(
            registry.model_lookup_candidates(
                provider_id="ollama",
                model_name="llama3.2:latest",
            ),
            ["llama3.2:latest", "llama3.2"],
        )
        self.assertEqual(
            registry.model_lookup_candidates(
                provider_id="lmstudio",
                model_name="loaded-model",
            ),
            ["loaded-model"],
        )

    def test_registry_validates_or_pulls_ollama_model_with_existing_behaviour(self) -> None:
        logger = _FakeLogger()
        registry = ProviderRegistry(logger=logger)

        with patch(
            "model.provider_registry.subprocess.check_output",
            return_value="NAME ID SIZE\nllama3.2:latest abc 1GB\n",
        ) as check_output, patch("model.provider_registry.subprocess.run") as run:
            registry.validate_or_prepare_model(
                provider_id="ollama",
                service_url="http://127.0.0.1:11434",
                model_name="llama3.2:latest",
            )

        check_output.assert_called_once_with(["ollama", "list"], text=True)
        run.assert_not_called()

    def test_registry_pulls_missing_ollama_model(self) -> None:
        registry = ProviderRegistry(logger=_FakeLogger())

        with patch(
            "model.provider_registry.subprocess.check_output",
            return_value="NAME ID SIZE\nother:latest abc 1GB\n",
        ), patch("model.provider_registry.subprocess.run") as run:
            registry.validate_or_prepare_model(
                provider_id="ollama",
                service_url="http://127.0.0.1:11434",
                model_name="llama3.2",
            )

        run.assert_called_once_with(["ollama", "pull", "llama3.2"], check=True)

    def test_registry_validates_lmstudio_loaded_model_with_existing_behaviour(self) -> None:
        response = type(
            "_Response",
            (),
            {
                "json": lambda self: {"data": [{"id": "loaded-model"}]},
                "raise_for_status": lambda self: None,
            },
        )()
        registry = ProviderRegistry(logger=_FakeLogger())

        with patch("model.provider_registry.requests.get", return_value=response) as get:
            registry.validate_or_prepare_model(
                provider_id="lmstudio",
                service_url="http://127.0.0.1:1234",
                model_name="loaded-model",
            )

        get.assert_called_once_with(
            "http://127.0.0.1:1234/v1/models",
            timeout=10,
        )

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

    def test_stream_prompt_deltas_captures_final_ollama_usage(self) -> None:
        connector = _StubOllamaConnector(chat_results=[])
        connector.model_name = "llama3.2"
        connector.service_url = "http://127.0.0.1:11434"
        connector._connect_timeout = 5
        connector._read_timeout = 30
        usage = []
        frames = [
            {
                "message": {"content": "Hello"},
                "done": False,
            },
            {
                "message": {"content": ""},
                "done": True,
                "prompt_eval_count": 11,
                "eval_count": 7,
                "prompt_eval_duration": 100,
                "eval_duration": 200,
            },
        ]

        with patch(
            "model.llm_connector.requests.post",
            return_value=_FakeStreamResponse(frames),
        ):
            deltas = list(
                connector.stream_prompt_deltas(
                    prompt_type="U",
                    prompt="Hello",
                    on_usage_metadata=usage.append,
                )
            )

        self.assertEqual(deltas, ["Hello"])
        self.assertEqual(len(usage), 1)
        self.assertEqual(usage[0].prompt_tokens, 11)
        self.assertEqual(usage[0].completion_tokens, 7)
        self.assertEqual(usage[0].total_tokens, 18)
        self.assertEqual(usage[0].raw["prompt_eval_duration"], 100)

    def test_native_streaming_provider_yields_each_delta_without_fallback(self) -> None:
        connector = _StubOllamaConnector(chat_results=[])
        connector.model_name = "llama3.2"
        connector.service_url = "http://127.0.0.1:11434"
        connector._connect_timeout = 5
        connector._read_timeout = 30
        frames = [
            {"message": {"content": "Hel"}, "done": False},
            {"message": {"content": "lo"}, "done": False},
            {"message": {"content": ""}, "done": True},
        ]

        with patch(
            "model.llm_connector.requests.post",
            return_value=_FakeStreamResponse(frames),
        ):
            deltas = list(
                connector.stream_prompt_deltas(
                    prompt_type="U",
                    prompt="Hello",
                )
            )

        self.assertEqual(deltas, ["Hel", "lo"])
        self.assertEqual(connector.chat_num_predicts, [])
        self.assertEqual(connector.generate_num_predicts, [])

    def test_fallback_streaming_provider_emits_single_non_streaming_delta(self) -> None:
        usage: list[LLMUsageMetadata] = []
        connector = _FallbackStreamingConnector(
            {
                "text": "complete response",
                "prompt_tokens": 3,
                "completion_tokens": 4,
                "total_tokens": 7,
            }
        )

        deltas = list(
            connector.stream_prompt_deltas(
                prompt_type="U",
                prompt="Hello",
                generation_options={"temperature": 0.3},
                on_usage_metadata=usage.append,
            )
        )

        self.assertEqual(deltas, ["complete response"])
        self.assertEqual(
            connector.calls,
            [("U", "Hello", False, {"temperature": 0.3})],
        )
        self.assertEqual(len(usage), 1)
        self.assertEqual(usage[0].prompt_tokens, 3)
        self.assertEqual(usage[0].completion_tokens, 4)
        self.assertEqual(usage[0].total_tokens, 7)

    def test_native_streaming_provider_propagates_backend_errors(self) -> None:
        connector = _StubOllamaConnector(chat_results=[])
        connector.model_name = "llama3.2"
        connector.service_url = "http://127.0.0.1:11434"
        connector._connect_timeout = 5
        connector._read_timeout = 30

        with patch(
            "model.llm_connector.requests.post",
            side_effect=RuntimeError("backend down"),
        ):
            with self.assertRaisesRegex(RuntimeError, "backend down"):
                list(
                    connector.stream_prompt_deltas(
                        prompt_type="U",
                        prompt="Hello",
                    )
                )

    def test_lmstudio_model_listing_uses_http_timeout(self) -> None:
        connector = LMStudioConnector.__new__(LMStudioConnector)
        connector.service_url = "http://127.0.0.1:1234"
        connector._connect_timeout = 5
        connector._read_timeout = 45
        response = type(
            "_Response",
            (),
            {"json": lambda self: {"data": [{"id": "loaded-model"}]}},
        )()

        with patch("model.llm_connector.requests.get", return_value=response) as get:
            models = connector.list_models()

        self.assertEqual(models, ["loaded-model"])
        get.assert_called_once_with(
            "http://127.0.0.1:1234/v1/models",
            timeout=(5, 45),
        )


if __name__ == "__main__":
    unittest.main()
