"""Deterministic tests for Ollama connector retry behaviour.

# Author: Clive Bostock
# Date: 2026-04-27
# Description: Verifies that Ollama completions retry with a larger
#   num_predict budget when done_reason indicates truncation.
"""

from __future__ import annotations

import json
import requests
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
    OpenAICompatibleConnector,
    OpenAICompatibleError,
    LLMUsageMetadata,
    OllamaConnector,
    normalise_generation_options,
    provider_generation_options,
)
from model.provider_registry import ProviderRegistry
from orac_core.knowledge.model_submission import StrictModelInvocationOptions
from orac_core.governed_retrieval.protocol import ToolStreamEventKind


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
        chat_results: list[dict[str, str] | Exception],
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
            result = self._chat_results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result
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
        self.assertEqual(registry.provider_ids(), ("lmstudio", "ollama", "openai_compatible"))

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
        self.assertEqual(capabilities.processing_locality, "LOCAL")
        self.assertTrue(capabilities.text_evidence_eligible)

    def test_lmstudio_capabilities_are_explicit(self) -> None:
        capabilities = ProviderRegistry().capabilities("lmstudio")

        self.assertFalse(capabilities.supports_native_streaming)
        self.assertTrue(capabilities.uses_fallback_streaming)
        self.assertTrue(capabilities.supports_usage_metadata)
        self.assertTrue(capabilities.supports_model_listing)
        self.assertFalse(capabilities.supports_model_details)
        self.assertFalse(capabilities.supports_model_pull)
        self.assertTrue(capabilities.requires_loaded_model)
        self.assertEqual(capabilities.processing_locality, "LOCAL")
        self.assertTrue(capabilities.text_evidence_eligible)

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

    def test_strict_submission_disables_growth_and_endpoint_fallback(self) -> None:
        connector = _StubOllamaConnector(
            chat_results=[{"text": "partial answer", "done_reason": "length"}],
            default_num_predict=200,
        )

        response = connector.send_prompt(
            prompt_type="U",
            prompt="Review the evidence.",
            invocation_options=StrictModelInvocationOptions(),
        )

        self.assertEqual(response, "partial answer")
        self.assertEqual(connector.chat_num_predicts, [2048])
        self.assertEqual(connector.generate_num_predicts, [])

    def test_strict_submission_retries_one_transient_pre_output_failure(self) -> None:
        connector = _StubOllamaConnector(
            chat_results=[
                requests.Timeout("timed out"),
                {"text": "complete answer", "done_reason": "stop"},
            ],
        )

        result = connector.send_prompt_with_meta(
            prompt_type="U",
            prompt="Review the evidence.",
            invocation_options=StrictModelInvocationOptions(),
        )

        self.assertEqual(result["text"], "complete answer")
        self.assertEqual(connector.chat_num_predicts, [2048, 2048])
        self.assertEqual(connector.generate_num_predicts, [])

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


class _SseResponse:
    """Deterministic context-managed SSE response."""

    def __init__(self, lines: list[bytes], status_code: int = 200) -> None:
        self.lines = lines
        self.status_code = status_code
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def iter_lines(self, chunk_size=512, decode_unicode=True):
        del decode_unicode
        assert chunk_size == 1
        yield from self.lines


class OpenAICompatibleConnectorTests(unittest.TestCase):
    """Verify outbound wire behaviour without a live inference service."""

    def _connector(self) -> OpenAICompatibleConnector:
        connector = OpenAICompatibleConnector.__new__(OpenAICompatibleConnector)
        connector.service_url = "https://inference.example"
        connector.model_name = "exact/model:1"
        connector._headers = {"Authorization": "Bearer test-secret"}
        connector._connect_timeout = 2
        connector._read_timeout = 20
        connector._total_timeout = 20
        connector._context_tokens = None
        return connector

    @staticmethod
    def _event(frame: dict) -> list[bytes]:
        return [b": keepalive", b"data: " + json.dumps(frame).encode(), b""]

    def test_base_url_accepts_origin_or_v1_without_double_prefix(self) -> None:
        for base_url in ("https://inference.example", "https://inference.example/v1"):
            with self.subTest(base_url=base_url), patch.object(
                LLMConnector, "__init__", return_value=None
            ):
                connector = OpenAICompatibleConnector("model", base_url)
                self.assertEqual(connector._endpoint("models"),
                                 "https://inference.example/v1/models")
        with patch.object(LLMConnector, "__init__", return_value=None):
            with self.assertRaises(ValueError):
                OpenAICompatibleConnector("model", "https://inference.example/custom")

    def test_context_limit_is_explicit_and_model_specific(self) -> None:
        connector = self._connector()
        self.assertIsNone(connector.runtime_context_observation().context_limit_tokens)
        connector._context_tokens = 8192
        connector._model_context_tokens = {"exact/model:1": 32768}
        with patch.object(connector, "list_models", return_value=["exact/model:1", "other"]):
            details = connector.list_model_details()
        self.assertEqual(
            {item["name"]: item["provider_declared_context_tokens"] for item in details},
            {"exact/model:1": 32768, "other": 8192},
        )

    def test_discovery_and_non_streaming_use_exact_model_and_auth(self) -> None:
        connector = self._connector()
        models_response = types.SimpleNamespace(
            status_code=200, json=lambda: {"data": [{"id": "exact/model:1"}, {"id": "alias"}]}
        )
        chat_response = types.SimpleNamespace(
            status_code=200,
            json=lambda: {
                "choices": [{"message": {"content": "hello"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1},
            },
        )
        with patch("model.llm_connector.requests.get", return_value=models_response) as get, patch(
            "model.llm_connector.requests.post", return_value=chat_response
        ) as post:
            self.assertEqual(connector.list_models(), ["exact/model:1", "alias"])
            result = connector.send_prompt_with_meta("U", "Hi")
        self.assertEqual(result["text"], "hello")
        self.assertNotIn("total_tokens", result)
        self.assertEqual(post.call_args.args[0], "https://inference.example/v1/chat/completions")
        self.assertEqual(post.call_args.kwargs["json"]["model"], "exact/model:1")
        self.assertEqual(get.call_args.kwargs["headers"], post.call_args.kwargs["headers"])

    def test_stream_yields_incrementally_and_reports_terminal_usage(self) -> None:
        connector = self._connector()
        lines = []
        lines += self._event({"choices": [{"delta": {"content": "hel"}}]})
        lines += self._event({"choices": [{"delta": {"reasoning_content": "hidden", "content": "lo"}}]})
        lines += self._event({"choices": [{"delta": {}, "finish_reason": "stop"}]})
        lines += self._event({"choices": [], "usage": {"prompt_tokens": 4, "completion_tokens": 2}})
        lines += [b"data: [DONE]", b""]
        response = _SseResponse(lines)
        usage = []
        with patch("model.llm_connector.requests.post", return_value=response):
            stream = connector.stream_prompt_deltas("U", "Hi", on_usage_metadata=usage.append)
            self.assertEqual(next(stream), "hel")
            self.assertFalse(response.closed)
            self.assertEqual(list(stream), ["lo"])
        self.assertTrue(response.closed)
        self.assertEqual(usage[0].prompt_tokens, 4)

    def test_stream_truncation_and_malformed_sse_fail(self) -> None:
        connector = self._connector()
        for lines, code in [
            ([b"data: {bad}", b""], "INFERENCE_STREAM_FRAME_INVALID"),
            (self._event({"choices": [{"delta": {"content": "partial"}}]}), "INFERENCE_STREAM_TRUNCATED"),
        ]:
            with self.subTest(code=code), patch(
                "model.llm_connector.requests.post", return_value=_SseResponse(lines)
            ):
                with self.assertRaises(OpenAICompatibleError) as raised:
                    list(connector.stream_prompt_deltas("U", "Hi"))
                self.assertEqual(raised.exception.code, code)

    def test_multiline_sse_data_frame_is_assembled(self) -> None:
        connector = self._connector()
        lines = [b'data: {"choices": [',
                 b'data: {"delta": {"content": "split"}}]}', b""]
        lines += self._event({"choices": [{"delta": {}, "finish_reason": "stop"}]})
        lines += [b"data: [DONE]", b""]
        with patch("model.llm_connector.requests.post", return_value=_SseResponse(lines)):
            self.assertEqual(list(connector.stream_prompt_deltas("U", "Hi")), ["split"])

    def test_tool_arguments_complete_before_core_receives_call(self) -> None:
        connector = self._connector()
        lines = []
        lines += self._event({"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1", "function": {"name": "retrieve", "arguments": '{"query":'}}]}}]})
        lines += self._event({"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '"x"}'}}]}}]})
        lines += self._event({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]})
        lines += [b"data: [DONE]", b""]
        with patch("model.llm_connector.requests.post", return_value=_SseResponse(lines)):
            events = list(connector.stream_tool_events(messages=[], tools=[]))
        self.assertEqual(
            [event.kind for event in events],
            [ToolStreamEventKind.TOOL_CALL_START,
             ToolStreamEventKind.TOOL_CALL_ARGUMENT_DELTA,
             ToolStreamEventKind.TOOL_CALL_COMPLETED,
             ToolStreamEventKind.ASSISTANT_COMPLETION],
        )
        self.assertEqual(events[1].arguments_delta, '{"query":"x"}')

    def test_tool_finish_without_done_exposes_no_executable_call(self) -> None:
        """A dropped terminal SSE frame cannot release a pending tool call."""
        connector = self._connector()
        lines = self._event({"choices": [{"delta": {"tool_calls": [{
            "index": 0, "id": "c1", "function": {
                "name": "retrieve", "arguments": '{"query":"x"}'
            }
        }]}}]})
        lines += self._event({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]})
        with patch("model.llm_connector.requests.post", return_value=_SseResponse(lines)):
            events = []
            with self.assertRaises(OpenAICompatibleError) as raised:
                for event in connector.stream_tool_events(messages=[], tools=[]):
                    events.append(event)
        self.assertEqual(raised.exception.code, "INFERENCE_STREAM_TRUNCATED")
        self.assertFalse(any(event.kind == ToolStreamEventKind.TOOL_CALL_COMPLETED for event in events))

    def test_auth_failure_is_structured_and_secret_free(self) -> None:
        connector = self._connector()
        response = types.SimpleNamespace(status_code=401)
        with patch("model.llm_connector.requests.get", return_value=response):
            with self.assertRaises(OpenAICompatibleError) as raised:
                connector.list_models()
        self.assertEqual(raised.exception.code, "INFERENCE_AUTHENTICATION_FAILED")
        self.assertNotIn("test-secret", str(raised.exception))
        with patch("model.llm_connector.requests.post", return_value=response):
            with self.assertRaises(OpenAICompatibleError) as chat_error:
                connector.send_prompt_with_meta("U", "Hi")
        self.assertEqual(chat_error.exception.code, "INFERENCE_AUTHENTICATION_FAILED")
        self.assertNotIn("test-secret", str(chat_error.exception))

    def test_cancelling_text_stream_closes_transport(self) -> None:
        connector = self._connector()
        response = _SseResponse(self._event({"choices": [{"delta": {"content": "first"}}]}))
        with patch("model.llm_connector.requests.post", return_value=response):
            stream = connector.stream_prompt_deltas("U", "Hi")
            self.assertEqual(next(stream), "first")
            stream.close()
        self.assertTrue(response.closed)

    def test_request_timeout_is_structured(self) -> None:
        connector = self._connector()
        with patch("model.llm_connector.requests.post", side_effect=requests.Timeout):
            with self.assertRaises(OpenAICompatibleError) as raised:
                connector.send_prompt_with_meta("U", "Hi")
        self.assertEqual(raised.exception.code, "INFERENCE_TIMEOUT")

    def test_redirect_is_not_followed_with_bearer_token(self) -> None:
        connector = self._connector()
        response = types.SimpleNamespace(status_code=302)
        with patch("model.llm_connector.requests.get", return_value=response) as get:
            with self.assertRaises(OpenAICompatibleError):
                connector.list_models()
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    def test_sse_backend_error_event_fails_without_completed_tool_call(self) -> None:
        connector = self._connector()
        lines = [b"event: error", b'data: {"error": "backend stopped"}', b""]
        with patch("model.llm_connector.requests.post", return_value=_SseResponse(lines)):
            with self.assertRaises(OpenAICompatibleError) as raised:
                list(connector.stream_tool_events(messages=[], tools=[]))
        self.assertEqual(raised.exception.code, "INFERENCE_BACKEND_ERROR")


if __name__ == "__main__":
    unittest.main()
