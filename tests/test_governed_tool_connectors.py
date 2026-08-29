"""Provider contract tests for normalized governed-tool events."""
# Author: Clive Bostock
# Date: 2026-08-29
# Description: Verifies Ollama and LM Studio wire frames stay behind connectors.

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.llm_connector import LMStudioConnector  # noqa: E402
from model.llm_connector import OllamaConnector  # noqa: E402
from model.provider_registry import ProviderRegistry  # noqa: E402
from orac_core.governed_retrieval import ToolStreamEventKind as Kind  # noqa: E402
from orac_core.governed_retrieval import StructuredToolCapabilityProbe  # noqa: E402
from orac_core.governed_retrieval import ToolStreamEvent  # noqa: E402


class _Response:
    """Minimal requests response fixture supporting stream and JSON paths."""

    def __init__(self, *, lines=(), payload=None):
        self.lines = list(lines)
        self.payload = payload or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    def iter_lines(self, decode_unicode=True):
        del decode_unicode
        yield from self.lines

    def json(self):
        return self.payload


def _ollama_connector():
    connector = object.__new__(OllamaConnector)
    connector.model_name = "fixture"
    connector.service_url = "http://ollama"
    connector._connect_timeout = 5
    connector._read_timeout = 60
    connector.default_num_predict = 100
    return connector


def _lmstudio_connector():
    connector = object.__new__(LMStudioConnector)
    connector.model_name = "fixture"
    connector.service_url = "http://lmstudio"
    connector._connect_timeout = 5
    connector._read_timeout = 60
    return connector


class GovernedToolConnectorContractTests(unittest.TestCase):
    """Compare equivalent provider-native tool streams after normalization."""

    def test_ollama_stream_normalizes_content_arguments_completion_and_usage(self):
        frames = [
            json.dumps({"message": {"content": "Checking "}, "done": False}),
            json.dumps(
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "c1",
                                "function": {
                                    "name": "retrieve",
                                    "arguments": '{"query":"image",',
                                },
                            }
                        ]
                    },
                    "done": False,
                }
            ),
            json.dumps(
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "c1",
                                "function": {
                                    "name": "retrieve",
                                    "arguments": '"domain":"CONVERSATION"}',
                                },
                            }
                        ]
                    },
                    "done": True,
                    "done_reason": "tool_calls",
                    "prompt_eval_count": 10,
                    "eval_count": 4,
                }
            ),
        ]
        with patch("model.llm_connector.requests.post", return_value=_Response(lines=frames)):
            events = list(
                _ollama_connector().stream_tool_events(
                    messages=[{"role": "user", "content": "x"}],
                    tools=[{"type": "function"}],
                )
            )
        kinds = [event.kind for event in events]
        self.assertIn(Kind.ASSISTANT_TEXT_DELTA, kinds)
        self.assertEqual(kinds.count(Kind.TOOL_CALL_START), 1)
        self.assertEqual(kinds.count(Kind.TOOL_CALL_ARGUMENT_DELTA), 2)
        self.assertIn(Kind.TOOL_CALL_COMPLETED, kinds)
        self.assertIn(Kind.USAGE, kinds)
        self.assertEqual(events[-1].finish_reason, "tool_calls")

    def test_ollama_context_limit_comes_from_structured_provider_metadata(self):
        payload = {
            "model_info": {
                "qwen.context_length": 49152,
                "vision.context_length": 65536,
            },
            "capabilities": ["completion", "tools"],
            "requires": "0.17.1",
            "parameters": "temperature 0.2\nnum_ctx 32768\ntop_p 0.9",
        }
        with patch("model.llm_connector.requests.post", return_value=_Response(payload=payload)):
            details = _ollama_connector().model_runtime_details("fixture")
        self.assertEqual(details["provider_declared_context_tokens"], 49152)
        self.assertEqual(details["runtime_execution_context_tokens"], 32768)
        self.assertEqual(
            details["provider_declared_capabilities"], ["completion", "tools"]
        )

    def test_runtime_observation_is_bounded_and_rereadable(self):
        payload = {
            "model_info": {"qwen.context_length": 49152},
            "parameters": "num_ctx 32768",
            "requires": "0.17.1",
        }
        with patch(
            "model.llm_connector.requests.post",
            return_value=_Response(payload=payload),
        ):
            observation = _ollama_connector().runtime_context_observation()
        self.assertEqual(observation.context_limit_tokens, 32768)
        self.assertEqual(observation.source_code, "OLLAMA_SHOW")
        self.assertTrue(observation.can_reliably_reread)
        self.assertEqual(len(observation.observation_fingerprint or ""), 64)

    def test_model_capability_without_num_ctx_keeps_runtime_limit_unknown(self):
        payload = {
            "model_info": {"qwen.context_length": 49152},
            "parameters": "temperature 0.2",
        }
        with patch(
            "model.llm_connector.requests.post",
            return_value=_Response(payload=payload),
        ):
            observation = _ollama_connector().runtime_context_observation()
        self.assertIsNone(observation.context_limit_tokens)
        self.assertEqual(observation.source_code, "OLLAMA_SHOW")

    def test_exact_provider_serializations_include_context_framing(self):
        messages = [{"role": "user", "content": "question"}]
        tools = [{"type": "function", "function": {"name": "retrieve"}}]

        ollama_serialized, ollama_code = (
            _ollama_connector().provider_context_serialization(
                messages=messages,
                tools=tools,
            )
        )
        lm_serialized, lm_code = (
            _lmstudio_connector().provider_context_serialization(
                messages=messages,
                tools=tools,
            )
        )

        self.assertEqual(json.loads(ollama_serialized)["messages"], messages)
        self.assertEqual(json.loads(ollama_serialized)["tools"], tools)
        self.assertEqual(json.loads(lm_serialized)["messages"], messages)
        self.assertEqual(json.loads(lm_serialized)["tools"], tools)
        self.assertIn("OLLAMA", ollama_code)
        self.assertIn("LMSTUDIO", lm_code)

    def test_ollama_translates_ephemeral_tool_arguments_to_native_object(self):
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "c1",
                        "type": "function",
                        "function": {
                            "name": "retrieve",
                            "arguments": (
                                '{"query":"image","domain":"CONVERSATION"}'
                            ),
                        },
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "c1",
                "name": "retrieve",
                "content": '{"status":"no_evidence"}',
            },
        ]

        payload = _ollama_connector()._ollama_tool_payload(
            messages=messages,
            tools=[],
            generation_options={"num_predict": 32},
            stream=True,
        )

        self.assertEqual(
            payload["messages"][0]["tool_calls"][0]["function"]["arguments"],
            {"query": "image", "domain": "CONVERSATION"},
        )
        self.assertEqual(payload["messages"][1], messages[1])

    def test_lmstudio_stream_assembles_incremental_openai_tool_arguments(self):
        native = [
            {
                "choices": [
                    {"delta": {"content": "Checking "}, "finish_reason": None}
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "id": "c1",
                                    "function": {
                                        "name": "retrieve",
                                        "arguments": '{"query":"image",',
                                    },
                                }
                            ]
                        },
                        "finish_reason": None,
                    }
                ]
            },
            {
                "choices": [
                    {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": 0,
                                    "function": {
                                        "arguments": '"domain":"CONVERSATION"}'
                                    },
                                }
                            ]
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                },
            },
        ]
        lines = [f"data: {json.dumps(item)}" for item in native] + ["data: [DONE]"]
        with patch("model.llm_connector.requests.post", return_value=_Response(lines=lines)):
            events = list(
                _lmstudio_connector().stream_tool_events(
                    messages=[{"role": "user", "content": "x"}],
                    tools=[{"type": "function"}],
                )
            )
        kinds = [event.kind for event in events]
        self.assertEqual(kinds.count(Kind.TOOL_CALL_START), 1)
        self.assertEqual(kinds.count(Kind.TOOL_CALL_ARGUMENT_DELTA), 2)
        arguments = "".join(
            event.arguments_delta
            for event in events
            if event.kind is Kind.TOOL_CALL_ARGUMENT_DELTA
        )
        self.assertEqual(
            json.loads(arguments),
            {"query": "image", "domain": "CONVERSATION"},
        )
        self.assertEqual(events[-1].kind, Kind.USAGE)

    def test_buffered_fallback_and_capabilities_are_provider_not_model_named(self):
        payload = {
            "choices": [
                {
                    "message": {
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c1",
                                "function": {
                                    "name": "retrieve",
                                    "arguments": (
                                        '{"query":"image","domain":"CONVERSATION"}'
                                    ),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ]
        }
        with patch("model.llm_connector.requests.post", return_value=_Response(payload=payload)):
            events = list(
                _lmstudio_connector().buffered_tool_events(
                    messages=[{"role": "user", "content": "x"}],
                    tools=[{"type": "function"}],
                )
            )
        self.assertIn(Kind.TOOL_CALL_COMPLETED, [event.kind for event in events])
        for provider_id in ("ollama", "lmstudio"):
            capabilities = ProviderRegistry().capabilities(provider_id)
            self.assertTrue(capabilities.supports_structured_tool_calling)
            self.assertTrue(capabilities.supports_streamed_structured_tool_calling)

    def test_probe_measures_framing_without_executing_retrieval(self):
        class _ProbeConnector:
            def stream_tool_events(self, **kwargs):
                self.request = kwargs
                yield ToolStreamEvent(
                    Kind.TOOL_CALL_START,
                    call_id="c1",
                    tool_name="retrieve",
                )
                yield ToolStreamEvent(
                    Kind.TOOL_CALL_ARGUMENT_DELTA,
                    call_id="c1",
                    tool_name="retrieve",
                    arguments_delta=(
                        '{"query":"fixture","domain":"CONVERSATION"}'
                    ),
                )
                yield ToolStreamEvent(
                    Kind.TOOL_CALL_COMPLETED,
                    call_id="c1",
                    tool_name="retrieve",
                )
                yield ToolStreamEvent(Kind.ASSISTANT_COMPLETION, finish_reason="tool_calls")

        connector = _ProbeConnector()
        report = StructuredToolCapabilityProbe().run(connector)
        self.assertTrue(report.structured_framing_valid)
        self.assertTrue(report.streamed_framing_valid)
        self.assertEqual(report.tool_call_count, 1)
        self.assertEqual(report.visible_characters_before_tool, 0)
        self.assertEqual(report.reason_code, "PROBE_VERIFIED")
        self.assertEqual(connector.request["generation_options"]["num_predict"], 128)


if __name__ == "__main__":
    unittest.main()
