"""LLM connector implementations for Orac backends."""

# Author: Clive Bostock
# Date: 2026-04-27
# Description: Provides LM Studio and Ollama connector implementations for
#   Orac, including Ollama retry handling for truncated responses.

from model.orac_abc import LLMConnectorABC, MODEL_SERVICE_DESCRIPTORS
from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
import re
import time
from typing import Any, cast
from urllib.parse import urlparse, urlunparse
import requests
from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from lib.logutil import Logger
from orac_core.knowledge.model_submission import StrictModelInvocationOptions
from orac_core.governed_retrieval.protocol import ToolStreamEvent
from orac_core.governed_retrieval.protocol import ToolStreamEventKind
from orac_core.context_budget import RuntimeContextObservation


APP_HOME = project_home()
RESOURCES_DIR = APP_HOME / 'resources'
CONFIG_DIR = RESOURCES_DIR / 'config'
CONFIG_FILE_PATH = CONFIG_DIR / 'orac.ini'

GENERATION_OPTION_KEYS = {
    "temperature",
    "top_p",
    "top_k",
    "repeat_penalty",
    "num_predict",
    "seed",
}

OLLAMA_GENERATION_KEYS = {
    "temperature",
    "top_p",
    "top_k",
    "repeat_penalty",
    "num_predict",
    "seed",
}

OPENAI_COMPATIBLE_GENERATION_MAP = {
    "temperature": "temperature",
    "top_p": "top_p",
    "num_predict": "max_tokens",
}


@dataclass
class LLMUsageMetadata:
    """Token usage metadata returned by an LLM backend."""

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    raw: dict[str, Any] | None = None


LLMUsageMetadataCallback = Callable[[LLMUsageMetadata], None]


def _coerce_float(value: Any) -> float | None:
    """Return value as float, or None when it cannot be used safely."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _coerce_int(value: Any) -> int | None:
    """Return value as int, or None when it cannot be used safely."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None


def normalise_generation_options(options: dict[str, Any] | None) -> dict[str, Any]:
    """Return validated provider-neutral generation options.

    Unsupported or intentionally internal options such as ``num_ctx`` and
    stop sequences are omitted here. ``num_ctx`` belongs to runtime/model
    configuration, not request-style presets.
    """
    if not isinstance(options, dict):
        return {}

    normalised: dict[str, Any] = {}

    temperature = _coerce_float(options.get("temperature"))
    if temperature is not None:
        normalised["temperature"] = min(2.0, max(0.0, temperature))

    top_p = _coerce_float(options.get("top_p"))
    if top_p is not None:
        normalised["top_p"] = min(1.0, max(0.0, top_p))

    top_k = _coerce_int(options.get("top_k"))
    if top_k is not None and top_k >= 1:
        normalised["top_k"] = top_k

    repeat_penalty = _coerce_float(options.get("repeat_penalty"))
    if repeat_penalty is not None and repeat_penalty > 0:
        normalised["repeat_penalty"] = repeat_penalty

    num_predict = _coerce_int(options.get("num_predict"))
    if num_predict is not None and num_predict >= 1:
        normalised["num_predict"] = num_predict

    seed = _coerce_int(options.get("seed"))
    if seed is not None:
        normalised["seed"] = seed

    return normalised


def provider_generation_options(
    provider: str,
    options: dict[str, Any] | None,
) -> dict[str, Any]:
    """Map provider-neutral generation options to provider request fields."""
    clean = normalise_generation_options(options)
    provider_key = (provider or "").strip().lower()

    if provider_key == "ollama":
        return {
            key: value
            for key, value in clean.items()
            if key in OLLAMA_GENERATION_KEYS
        }

    if provider_key in {"openai", "lmstudio"}:
        # OpenAI-compatible backends vary on seed/repetition support, so only
        # pass the common request fields here. Adapter-specific capability
        # checks can opt in to additional fields later.
        mapped: dict[str, Any] = {}
        for source_key, target_key in OPENAI_COMPATIBLE_GENERATION_MAP.items():
            if source_key in clean:
                mapped[target_key] = clean[source_key]
        return mapped

    return {}


def strict_generation_options(
    options: dict[str, Any] | None,
    invocation_options: StrictModelInvocationOptions | None,
) -> dict[str, Any] | None:
    """Apply an immutable output cap for evidence-backed submissions."""
    if invocation_options is None:
        return options
    clean = normalise_generation_options(options)
    requested = _coerce_int(clean.get("num_predict"))
    if requested is not None and requested > invocation_options.max_output_tokens:
        raise ValueError("MAT_SUB_OUTPUT_RESERVE_EXCEEDED")
    clean["num_predict"] = invocation_options.max_output_tokens
    return clean


def _usage_metadata_from_result(
    result: dict[str, Any],
) -> LLMUsageMetadata | None:
    """Build usage metadata from a connector result dictionary.

    Args:
        result (dict[str, Any]): Connector response metadata.

    Returns:
        LLMUsageMetadata | None: Metadata when token counts are present.
    """
    prompt_tokens = _coerce_int(result.get("prompt_tokens"))
    completion_tokens = _coerce_int(result.get("completion_tokens"))
    total_tokens = _coerce_int(result.get("total_tokens"))
    if total_tokens is None and (
        prompt_tokens is not None or completion_tokens is not None
    ):
        total_tokens = (prompt_tokens or 0) + (completion_tokens or 0)
    if prompt_tokens is None and completion_tokens is None and total_tokens is None:
        return None
    if (
        total_tokens == 0
        and prompt_tokens in (None, 0)
        and completion_tokens in (None, 0)
    ):
        return None
    return LLMUsageMetadata(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        raw=dict(result),
    )


def _usage_metadata_from_ollama_response(
    data: dict[str, Any],
) -> LLMUsageMetadata | None:
    """Build usage metadata from Ollama's final streaming response.

    Args:
        data (dict[str, Any]): Final Ollama stream frame.

    Returns:
        LLMUsageMetadata | None: Token metadata when Ollama supplied it.
    """
    prompt_tokens = _coerce_int(data.get("prompt_eval_count"))
    completion_tokens = _coerce_int(data.get("eval_count"))
    if prompt_tokens is None and completion_tokens is None:
        return None
    return LLMUsageMetadata(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=(prompt_tokens or 0) + (completion_tokens or 0),
        raw=dict(data),
    )


class LLMConnector(LLMConnectorABC):
    def __init__(self, model_service_id: str):
        self.config_mgr = ConfigManager(config_file_path=CONFIG_FILE_PATH)
        self.llm_service_id = self.config_mgr.config_value(
            section='service', key='llm_service_id'
        )
        if model_service_id not in MODEL_SERVICE_DESCRIPTORS:
            valid_ids = ", ".join(MODEL_SERVICE_DESCRIPTORS.keys())
            message = (
                f'Invalid interface specification: "{model_service_id}". '
                f'Expected one of {valid_ids}'
            )
            raise ValueError(message)
        super().__init__(model_service_id)

    def list_models(self):
        """Return a list of available models within the LM service."""
        raise NotImplementedError(
            f"{self.__class__.__name__}.send_prompt() must be implemented in the subclass"
        )

    def list_model_details(self) -> list[dict[str, Any]]:
        """Return available models with any backend-provided metadata."""
        return []

    def runtime_context_observation(self) -> RuntimeContextObservation:
        """Return a bounded active context observation when reliably available."""
        return RuntimeContextObservation(
            context_limit_tokens=None,
            source_code=f"{self.interface_id().upper()}_UNAVAILABLE",
        )

    def provider_context_serialization(
        self,
        *,
        prompt: str | None = None,
        messages: Sequence[Mapping[str, Any]] | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
    ) -> tuple[str, str]:
        """Return the exact context-bearing provider invocation shape.

        Transport-only options such as endpoints, streaming flags, and output
        limits are excluded because they are not tokenised model context.
        """
        if prompt is not None and messages is not None:
            raise ValueError("prompt and messages are mutually exclusive")
        if prompt is None and messages is None:
            raise ValueError("prompt or messages is required")
        context_shape: dict[str, Any] = {
            "messages": (
                [dict(item) for item in messages]
                if messages is not None
                else [{"role": "user", "content": str(prompt or "")}]
            ),
        }
        if tools:
            context_shape["tools"] = [dict(item) for item in tools]
        serialized = json.dumps(
            context_shape,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return serialized, "PROVIDER_NEUTRAL_CHAT_V1"

    def switch_model(self, model_name):
        message = f"Switching models is not implemented for LLM Service {self.llm_service_id}"
        raise NotImplementedError(message)

    def send_prompt(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
        generation_options: dict[str, Any] | None = None,
        invocation_options: StrictModelInvocationOptions | None = None,
    ) -> str:
        """
        Send a prompt to the LLM backend and return the response.

        Args:
            prompt_type (str): 'C' for conditioning prompt, 'U' for user dialogue.
            prompt (str): The prompt text to send.
            stream (bool): Whether to request streaming response.

        Returns:
            str: The LLM's textual response.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.send_prompt() must be implemented in the subclass"
        )

    def send_prompt_with_meta(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
        generation_options: dict[str, Any] | None = None,
        invocation_options: StrictModelInvocationOptions | None = None,
    ) -> dict[str, Any]:
        """Send a prompt and return response text with optional usage metadata."""
        call_kwargs = {
            "prompt_type": prompt_type,
            "prompt": prompt,
            "stream": stream,
            "generation_options": strict_generation_options(
                generation_options,
                invocation_options,
            ),
        }
        if invocation_options is not None:
            call_kwargs["invocation_options"] = invocation_options
        raw = self.send_prompt(**call_kwargs)
        if hasattr(raw, "content"):
            text = raw.content
        else:
            text = raw
        return {
            "text": text if isinstance(text, str) else str(text),
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def stream_prompt_deltas(
        self,
        prompt_type: str,
        prompt: str,
        generation_options: dict[str, Any] | None = None,
        on_usage_metadata: LLMUsageMetadataCallback | None = None,
        invocation_options: StrictModelInvocationOptions | None = None,
    ) -> Iterator[str]:
        """Yield streamed response text deltas.

        Connectors without a native streaming implementation fall back to
        the existing non-streaming path and emit one final delta.
        """
        call_kwargs = {
            "prompt_type": prompt_type,
            "prompt": prompt,
            "stream": False,
            "generation_options": generation_options,
        }
        if invocation_options is not None:
            call_kwargs["invocation_options"] = invocation_options
        result = self.send_prompt_with_meta(**call_kwargs)
        if on_usage_metadata is not None:
            usage = _usage_metadata_from_result(result)
            if usage is not None:
                on_usage_metadata(usage)
        text = result.get("text", "")
        yield text if isinstance(text, str) else str(text)

    def stream_tool_events(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
        generation_options: dict[str, Any] | None = None,
    ) -> Iterator[ToolStreamEvent]:
        """Yield normalized streamed structured-tool events."""
        del messages, tools, generation_options
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support streamed structured tools"
        )

    def buffered_tool_events(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
        generation_options: dict[str, Any] | None = None,
    ) -> Iterator[ToolStreamEvent]:
        """Yield normalized events from one buffered structured-tool decision."""
        del messages, tools, generation_options
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support structured tools"
        )

    def interface_name(self) -> str:
        """Return the backend name (e.g. 'LM Studio', 'Ollama', etc)."""
        return MODEL_SERVICE_DESCRIPTORS[self.model_interface_id]

    def interface_id(self) -> str:
        """Return the backend ID (e.g. 'lmstudio', 'ollama')."""
        return self.model_interface_id


class LMStudioConnector(LLMConnector):
    def __init__(self, model_name: str, service_url: str):
        super().__init__("lmstudio")
        self.logger = Logger()
        # 🧹 Defensive strip
        self.model_name = model_name.strip()
        clean_url = service_url.strip()

        # 🧱 Normalize URL
        parsed_url = urlparse(clean_url)
        if not parsed_url.scheme:
            clean_url = f"http://{clean_url}"
            parsed_url = urlparse(clean_url)
        clean_url = urlunparse(parsed_url._replace(path="")).rstrip("/")

        self.logger.log_info(f"🔗 LMStudio base_url: '{clean_url}'")
        self.logger.log_info(f"📝 LMStudio model: '{self.model_name}'")

        self.service_url = clean_url
        req_to = int(
            self.config_mgr.config_value(
                "service",
                "llm_timeout",
                default=self.config_mgr.config_value(
                    "client",
                    "llm_timeout",
                    default="60",
                ),
            )
        )
        self._connect_timeout = 5
        self._read_timeout = max(30, req_to)
        self.llm_session = ChatOpenAI(
            base_url=self.service_url + "/v1",
            api_key=cast(SecretStr, "not-needed"),  # LM Studio ignores this
            model=self.model_name
        )

    def _invoke_with_generation_options(
        self,
        prompt: str,
        generation_options: dict[str, Any] | None = None,
        invocation_options: StrictModelInvocationOptions | None = None,
    ) -> Any:
        """Invoke LM Studio with OpenAI-compatible options when available."""
        request_options = provider_generation_options(
            "lmstudio",
            strict_generation_options(generation_options, invocation_options),
        )
        if request_options and hasattr(self.llm_session, "bind"):
            return self.llm_session.bind(**request_options).invoke(prompt)
        return self.llm_session.invoke(prompt)

    def send_prompt(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
        generation_options: dict[str, Any] | None = None,
        invocation_options: StrictModelInvocationOptions | None = None,
    ) -> str:
        """Send prompt to LM Studio."""
        self.logger.log_info(f"📤 Sending prompt to LM Studio (stream={stream})...")
        return self._invoke_with_generation_options(
            prompt,
            generation_options,
            invocation_options,
        )

    def send_prompt_with_meta(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
        generation_options: dict[str, Any] | None = None,
        invocation_options: StrictModelInvocationOptions | None = None,
    ) -> dict[str, Any]:
        """Send prompt to LM Studio and return text with token metadata when available."""
        self.logger.log_info(f"📤 Sending prompt to LM Studio (stream={stream})...")
        raw = self._invoke_with_generation_options(
            prompt,
            generation_options,
            invocation_options,
        )
        text = raw.content if hasattr(raw, "content") else raw
        usage = getattr(raw, "usage_metadata", None) or {}
        prompt_tokens = int(
            usage.get("input_tokens")
            or usage.get("prompt_tokens")
            or 0
        )
        completion_tokens = int(
            usage.get("output_tokens")
            or usage.get("completion_tokens")
            or 0
        )
        total_tokens = int(
            usage.get("total_tokens")
            or (prompt_tokens + completion_tokens)
        )
        response_metadata = getattr(raw, "response_metadata", None) or {}
        return {
            "text": text if isinstance(text, str) else str(text),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "done_reason": str(
                response_metadata.get("finish_reason")
                or response_metadata.get("stop_reason")
                or ""
            ),
        }

    def list_models(self):
        """List available models from LM Studio."""
        response = requests.get(
            f"{self.service_url}/v1/models",
            timeout=(
                getattr(self, "_connect_timeout", 5),
                getattr(self, "_read_timeout", 60),
            ),
        )
        return [model["id"] for model in response.json().get("data", [])]

    def provider_context_serialization(
        self,
        *,
        prompt: str | None = None,
        messages: Sequence[Mapping[str, Any]] | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
    ) -> tuple[str, str]:
        """Serialize LM Studio's OpenAI-compatible context-bearing fields."""
        if prompt is not None and messages is not None:
            raise ValueError("prompt and messages are mutually exclusive")
        if prompt is None and messages is None:
            raise ValueError("prompt or messages is required")
        payload: dict[str, Any] = {
            "messages": (
                [dict(item) for item in messages]
                if messages is not None
                else [{"role": "user", "content": str(prompt or "")}]
            )
        }
        if tools:
            payload["tools"] = [dict(item) for item in tools]
            payload["tool_choice"] = "auto"
        return (
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "LMSTUDIO_OPENAI_CHAT_CONTEXT_V1",
        )

    def _openai_tool_payload(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
        generation_options: dict[str, Any] | None,
        stream: bool,
    ) -> dict[str, Any]:
        """Build one OpenAI-compatible request without exposing wire details."""
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [dict(item) for item in messages],
            "stream": stream,
        }
        if tools:
            payload["tools"] = [dict(item) for item in tools]
            payload["tool_choice"] = "auto"
        payload.update(provider_generation_options("lmstudio", generation_options))
        return payload

    def stream_tool_events(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
        generation_options: dict[str, Any] | None = None,
    ) -> Iterator[ToolStreamEvent]:
        """Normalize LM Studio OpenAI-compatible streamed tool deltas."""
        payload = self._openai_tool_payload(
            messages=messages,
            tools=tools,
            generation_options=generation_options,
            stream=True,
        )
        calls: dict[int, dict[str, str]] = {}
        with requests.post(
            f"{self.service_url}/v1/chat/completions",
            json=payload,
            stream=True,
            timeout=(self._connect_timeout, self._read_timeout),
        ) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                line = str(raw_line).strip()
                if not line.startswith("data:"):
                    continue
                body = line[5:].strip()
                if body == "[DONE]":
                    break
                try:
                    frame = json.loads(body)
                except (TypeError, ValueError, json.JSONDecodeError):
                    yield ToolStreamEvent(
                        ToolStreamEventKind.ERROR,
                        error_code="LMSTUDIO_STREAM_FRAME_INVALID",
                    )
                    return
                choices = frame.get("choices") or []
                if choices:
                    choice = choices[0] if isinstance(choices[0], dict) else {}
                    delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
                    content = delta.get("content")
                    if content:
                        yield ToolStreamEvent(
                            ToolStreamEventKind.ASSISTANT_TEXT_DELTA,
                            text=str(content),
                        )
                    reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                    if reasoning:
                        yield ToolStreamEvent(
                            ToolStreamEventKind.REASONING_DELTA,
                            text=str(reasoning),
                        )
                    for native_call in delta.get("tool_calls") or []:
                        if not isinstance(native_call, dict):
                            continue
                        index = int(native_call.get("index") or 0)
                        function = native_call.get("function") or {}
                        record = calls.get(index)
                        if record is None:
                            record = {
                                "id": str(native_call.get("id") or f"call_{index}"),
                                "name": str(function.get("name") or ""),
                            }
                            calls[index] = record
                            yield ToolStreamEvent(
                                ToolStreamEventKind.TOOL_CALL_START,
                                call_id=record["id"],
                                call_index=index,
                                tool_name=record["name"],
                            )
                        elif function.get("name"):
                            record["name"] += str(function["name"])
                        arguments = function.get("arguments")
                        if arguments:
                            yield ToolStreamEvent(
                                ToolStreamEventKind.TOOL_CALL_ARGUMENT_DELTA,
                                call_id=record["id"],
                                call_index=index,
                                tool_name=record["name"],
                                arguments_delta=str(arguments),
                            )
                    finish_reason = str(choice.get("finish_reason") or "")
                    if finish_reason:
                        for index, record in sorted(calls.items()):
                            yield ToolStreamEvent(
                                ToolStreamEventKind.TOOL_CALL_COMPLETED,
                                call_id=record["id"],
                                call_index=index,
                                tool_name=record["name"],
                            )
                        yield ToolStreamEvent(
                            ToolStreamEventKind.ASSISTANT_COMPLETION,
                            finish_reason=finish_reason,
                        )
                usage = frame.get("usage")
                if isinstance(usage, dict):
                    yield ToolStreamEvent(ToolStreamEventKind.USAGE, usage=usage)

    def buffered_tool_events(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
        generation_options: dict[str, Any] | None = None,
    ) -> Iterator[ToolStreamEvent]:
        """Normalize one buffered LM Studio tool decision."""
        payload = self._openai_tool_payload(
            messages=messages,
            tools=tools,
            generation_options=generation_options,
            stream=False,
        )
        response = requests.post(
            f"{self.service_url}/v1/chat/completions",
            json=payload,
            timeout=(self._connect_timeout, self._read_timeout),
        )
        response.raise_for_status()
        frame = response.json()
        choices = frame.get("choices") or []
        choice = choices[0] if choices and isinstance(choices[0], dict) else {}
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        if message.get("content"):
            yield ToolStreamEvent(
                ToolStreamEventKind.ASSISTANT_TEXT_DELTA,
                text=str(message["content"]),
            )
        for index, native_call in enumerate(message.get("tool_calls") or []):
            if not isinstance(native_call, dict):
                continue
            function = native_call.get("function") or {}
            call_id = str(native_call.get("id") or f"call_{index}")
            name = str(function.get("name") or "")
            yield ToolStreamEvent(
                ToolStreamEventKind.TOOL_CALL_START,
                call_id=call_id,
                call_index=index,
                tool_name=name,
            )
            yield ToolStreamEvent(
                ToolStreamEventKind.TOOL_CALL_ARGUMENT_DELTA,
                call_id=call_id,
                call_index=index,
                tool_name=name,
                arguments_delta=str(function.get("arguments") or ""),
            )
            yield ToolStreamEvent(
                ToolStreamEventKind.TOOL_CALL_COMPLETED,
                call_id=call_id,
                call_index=index,
                tool_name=name,
            )
        usage = frame.get("usage")
        if isinstance(usage, dict):
            yield ToolStreamEvent(ToolStreamEventKind.USAGE, usage=usage)
        yield ToolStreamEvent(
            ToolStreamEventKind.ASSISTANT_COMPLETION,
            finish_reason=str(choice.get("finish_reason") or "stop"),
        )


class OllamaConnector(LLMConnector):
    def __init__(self, model_name: str, service_url: str):
        super().__init__("ollama")
        self.logger = Logger()
        self.logger.log_info('OllamaConnector instantiated')
        self.model_name = model_name.strip()
        clean_url = service_url.strip()
        parsed_url = urlparse(clean_url)
        if not parsed_url.scheme:
            clean_url = f"http://{clean_url}"
            parsed_url = urlparse(clean_url)
        self.service_url = urlunparse(parsed_url._replace(path="")).rstrip("/")

        self.logger.log_info(f"🔗 Ollama base_url: '{self.service_url}'")
        self.logger.log_info(f"📝 Ollama model: '{self.model_name}'")


        # config -> default hide reasoning (strip_reasoning_tags=true => default_show_reasoning False)
        strip_reasoning = (
            self.config_mgr.config_value(
                "settings",
                "strip_reasoning_tags_default",
                default=self.config_mgr.config_value(
                    "settings",
                    "strip_reasoning_tags",
                    default="true",
                ),
            )
            .strip().lower() in {"1", "true", "yes", "on", "y"}
        )
        self.default_show_reasoning = not strip_reasoning

        # HTTP timeouts. Prefer the service setting when present, otherwise
        # honour the client-facing timeout used by the local slave display.
        req_to = int(
            self.config_mgr.config_value(
                "service",
                "llm_timeout",
                default=self.config_mgr.config_value(
                    "client",
                    "llm_timeout",
                    default="60",
                ),
            )
        )
        self._connect_timeout = 5
        self._read_timeout = max(30, req_to)
        self.default_num_predict = max(
            1,
            self.config_mgr.int_config_value(
                "service",
                "default_num_predict",
                default=2048,
            ),
        )
        self.num_predict_incr_pct = max(
            1,
            self.config_mgr.int_config_value(
                "service",
                "num_predict_incr_pct",
                default=100,
            ),
        )
        self._max_num_predict_retries = 2
        self.keep_alive = self.config_mgr.config_value(
            "service", "keep_alive", default="30m"
        ).strip() or "30m"

        # Keep the connector hint minimal. User-facing behaviour belongs in
        # Orac's main system prompt policy, not the transport wrapper.
        self.system_hint = (
            "You are Orac. If the user poses a hypothetical or "
            "counterfactual premise, answer under that premise and do not "
            "correct it unless the user explicitly asks you to verify facts."
        )

    # ---------- helpers ----------

    def _strip_visible_think(self, text: str) -> str:
        """Remove <think>…</think>; if closing tag missing, drop from <think> to end."""
        if not isinstance(text, str):
            return ""
        if "<think>" in text and "</think>" not in text:  # dangling / truncated block
            return text.split("<think>", 1)[0].strip()
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    def _post_json(self, url: str, payload: dict) -> dict:
        t0 = time.perf_counter()
        r = requests.post(url, json=payload, timeout=(self._connect_timeout, self._read_timeout))
        r.raise_for_status()
        data = r.json()
        dt = time.perf_counter() - t0
        model = data.get("model") or self.model_name
        done = data.get("done_reason")
        pe = data.get("prompt_eval_count")
        ce = data.get("eval_count")
        self.logger.log_info(f"⏱️ Ollama RT: {dt:.2f}s model={model} done={done} pe={pe} ce={ce}")
        return data

    def _next_num_predict(self, current_num_predict: int) -> int:
        """Return the next token budget after a truncated response."""
        increment = max(
            1,
            math.ceil(current_num_predict * (self.num_predict_incr_pct / 100.0)),
        )
        return current_num_predict + increment

    def _initial_num_predict(
        self,
        generation_options: dict[str, Any] | None,
        invocation_options: StrictModelInvocationOptions | None = None,
    ) -> int:
        """Return the initial completion budget for this request."""
        options = normalise_generation_options(
            strict_generation_options(generation_options, invocation_options)
        )
        return int(options.get("num_predict") or self.default_num_predict)

    def _ollama_options(
        self,
        *,
        num_predict: int,
        generation_options: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build Ollama request options for one generation attempt."""
        request_options = {
            "num_predict": int(num_predict),
            "temperature": 0.2,
            "repeat_penalty": 1.1,
        }
        overrides = provider_generation_options("ollama", generation_options)
        overrides.pop("num_predict", None)
        request_options.update(overrides)
        return request_options

    def _chat_once(
        self,
        prompt: str,
        *,
        show_reasoning: bool,
        num_predict: int,
        use_system: bool,
        generation_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.service_url}/api/chat"
        msgs = [{"role": "user", "content": prompt}]
        if use_system and self.system_hint:
            msgs.insert(0, {"role": "system", "content": self.system_hint})

        payload = {
            "model": self.model_name,
            "messages": msgs,
            "stream": False,
            "keep_alive": getattr(self, "keep_alive", "30m"),
            "think": bool(show_reasoning),   # we’ll force False in send_prompt
            "options": self._ollama_options(
                num_predict=num_predict,
                generation_options=generation_options,
            ),
        }
        self.logger.log_info(
            f"➡️ /api/chat think={payload['think']} stream={payload['stream']} "
            f"np={payload['options']['num_predict']} sys={use_system}"
        )
        data = self._post_json(url, payload)
        text = (data.get("message") or {}).get("content") or data.get("response") or ""
        return {
            "text": text if isinstance(text, str) else str(text),
            "done_reason": data.get("done_reason"),
            "prompt_tokens": int(data.get("prompt_eval_count") or 0),
            "completion_tokens": int(data.get("eval_count") or 0),
            "total_tokens": int(data.get("prompt_eval_count") or 0) + int(data.get("eval_count") or 0),
            **{
                key: data.get(key)
                for key in (
                    "load_duration", "prompt_eval_duration", "eval_duration", "total_duration"
                )
                if data.get(key) is not None
            },
        }

    def _generate_once(
        self,
        prompt: str,
        *,
        num_predict: int,
        generation_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.service_url}/api/generate"
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            "keep_alive": getattr(self, "keep_alive", "30m"),
            "options": self._ollama_options(
                num_predict=num_predict,
                generation_options=generation_options,
            ),
        }
        self.logger.log_info(f"➡️ /api/generate np={num_predict}")
        data = self._post_json(url, payload)
        text = data.get("response") or ""
        return {
            "text": text if isinstance(text, str) else str(text),
            "done_reason": data.get("done_reason"),
            "prompt_tokens": int(data.get("prompt_eval_count") or 0),
            "completion_tokens": int(data.get("eval_count") or 0),
            "total_tokens": int(data.get("prompt_eval_count") or 0) + int(data.get("eval_count") or 0),
            **{
                key: data.get(key)
                for key in (
                    "load_duration", "prompt_eval_duration", "eval_duration", "total_duration"
                )
                if data.get(key) is not None
            },
        }

    def _chat_stream(
        self,
        prompt: str,
        *,
        show_reasoning: bool,
        num_predict: int,
        use_system: bool,
        generation_options: dict[str, Any] | None = None,
        on_usage_metadata: LLMUsageMetadataCallback | None = None,
    ) -> Iterator[str]:
        """Yield native Ollama chat stream response deltas."""
        url = f"{self.service_url}/api/chat"
        msgs = [{"role": "user", "content": prompt}]
        if use_system and self.system_hint:
            msgs.insert(0, {"role": "system", "content": self.system_hint})

        payload = {
            "model": self.model_name,
            "messages": msgs,
            "stream": True,
            "keep_alive": getattr(self, "keep_alive", "30m"),
            "think": bool(show_reasoning),
            "options": self._ollama_options(
                num_predict=num_predict,
                generation_options=generation_options,
            ),
        }
        self.logger.log_info(
            f"➡️ /api/chat think={payload['think']} stream={payload['stream']} "
            f"np={payload['options']['num_predict']} sys={use_system}"
        )

        with requests.post(
            url,
            json=payload,
            stream=True,
            timeout=(self._connect_timeout, self._read_timeout),
        ) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                try:
                    data = json.loads(raw_line)
                except Exception:
                    self.logger.log_warning(
                        f"Ignoring invalid Ollama stream line: {raw_line!r}"
                    )
                    continue

                delta = (data.get("message") or {}).get("content")
                if delta is None:
                    delta = data.get("response")
                if delta:
                    yield str(delta)
                if data.get("done") is True:
                    usage = _usage_metadata_from_ollama_response(data)
                    if usage is not None and on_usage_metadata is not None:
                        on_usage_metadata(usage)
                    break

    def _ollama_tool_payload(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
        generation_options: dict[str, Any] | None,
        stream: bool,
    ) -> dict[str, Any]:
        """Build one native Ollama structured chat request."""
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": self._ollama_tool_messages(messages),
            "stream": stream,
            "keep_alive": getattr(self, "keep_alive", "30m"),
            "think": False,
            "options": self._ollama_options(
                num_predict=self._initial_num_predict(generation_options),
                generation_options=generation_options,
            ),
        }
        if tools:
            payload["tools"] = [dict(item) for item in tools]
        return payload

    @staticmethod
    def _ollama_tool_messages(
        messages: Sequence[Mapping[str, Any]],
    ) -> list[dict[str, Any]]:
        """Translate provider-neutral tool transcripts to native Ollama messages."""
        native_messages: list[dict[str, Any]] = []
        for message in messages:
            native_message = dict(message)
            native_calls: list[dict[str, Any]] = []
            for call in message.get("tool_calls") or []:
                if not isinstance(call, Mapping):
                    continue
                native_call = dict(call)
                function = call.get("function")
                if isinstance(function, Mapping):
                    native_function = dict(function)
                    arguments = function.get("arguments")
                    if isinstance(arguments, str):
                        try:
                            parsed_arguments = json.loads(arguments)
                        except (TypeError, ValueError, json.JSONDecodeError) as exc:
                            raise ValueError(
                                "invalid provider-neutral tool arguments"
                            ) from exc
                        if not isinstance(parsed_arguments, dict):
                            raise ValueError(
                                "provider-neutral tool arguments must be an object"
                            )
                        native_function["arguments"] = parsed_arguments
                    native_call["function"] = native_function
                native_calls.append(native_call)
            if "tool_calls" in native_message:
                native_message["tool_calls"] = native_calls
            native_messages.append(native_message)
        return native_messages

    @staticmethod
    def _ollama_argument_fragment(value: Any) -> str:
        """Return one exact JSON argument fragment from Ollama framing."""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return ""

    def stream_tool_events(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
        generation_options: dict[str, Any] | None = None,
    ) -> Iterator[ToolStreamEvent]:
        """Normalize native Ollama streamed content and tool calls."""
        payload = self._ollama_tool_payload(
            messages=messages,
            tools=tools,
            generation_options=generation_options,
            stream=True,
        )
        calls: dict[int, dict[str, str]] = {}
        with requests.post(
            f"{self.service_url}/api/chat",
            json=payload,
            stream=True,
            timeout=(self._connect_timeout, self._read_timeout),
        ) as response:
            response.raise_for_status()
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                try:
                    frame = json.loads(raw_line)
                except (TypeError, ValueError, json.JSONDecodeError):
                    yield ToolStreamEvent(
                        ToolStreamEventKind.ERROR,
                        error_code="OLLAMA_STREAM_FRAME_INVALID",
                    )
                    return
                message = frame.get("message") if isinstance(frame.get("message"), dict) else {}
                content = message.get("content")
                if content:
                    yield ToolStreamEvent(
                        ToolStreamEventKind.ASSISTANT_TEXT_DELTA,
                        text=str(content),
                    )
                thinking = message.get("thinking")
                if thinking:
                    yield ToolStreamEvent(
                        ToolStreamEventKind.REASONING_DELTA,
                        text=str(thinking),
                    )
                for index, native_call in enumerate(message.get("tool_calls") or []):
                    if not isinstance(native_call, dict):
                        continue
                    function = native_call.get("function") or {}
                    record = calls.get(index)
                    if record is None:
                        record = {
                            "id": str(native_call.get("id") or f"call_{index}"),
                            "name": str(function.get("name") or ""),
                        }
                        calls[index] = record
                        yield ToolStreamEvent(
                            ToolStreamEventKind.TOOL_CALL_START,
                            call_id=record["id"],
                            call_index=index,
                            tool_name=record["name"],
                        )
                    arguments = self._ollama_argument_fragment(function.get("arguments"))
                    if arguments:
                        yield ToolStreamEvent(
                            ToolStreamEventKind.TOOL_CALL_ARGUMENT_DELTA,
                            call_id=record["id"],
                            call_index=index,
                            tool_name=record["name"],
                            arguments_delta=arguments,
                        )
                if frame.get("done") is True:
                    for index, record in sorted(calls.items()):
                        yield ToolStreamEvent(
                            ToolStreamEventKind.TOOL_CALL_COMPLETED,
                            call_id=record["id"],
                            call_index=index,
                            tool_name=record["name"],
                        )
                    usage = _usage_metadata_from_ollama_response(frame)
                    if usage is not None:
                        yield ToolStreamEvent(
                            ToolStreamEventKind.USAGE,
                            usage={
                                "prompt_tokens": usage.prompt_tokens,
                                "completion_tokens": usage.completion_tokens,
                                "total_tokens": usage.total_tokens,
                            },
                        )
                    yield ToolStreamEvent(
                        ToolStreamEventKind.ASSISTANT_COMPLETION,
                        finish_reason=(
                            "tool_calls"
                            if calls
                            else str(frame.get("done_reason") or "stop")
                        ),
                    )
                    break

    def buffered_tool_events(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
        generation_options: dict[str, Any] | None = None,
    ) -> Iterator[ToolStreamEvent]:
        """Normalize one buffered Ollama structured-tool decision."""
        payload = self._ollama_tool_payload(
            messages=messages,
            tools=tools,
            generation_options=generation_options,
            stream=False,
        )
        frame = self._post_json(f"{self.service_url}/api/chat", payload)
        message = frame.get("message") if isinstance(frame.get("message"), dict) else {}
        if message.get("content"):
            yield ToolStreamEvent(
                ToolStreamEventKind.ASSISTANT_TEXT_DELTA,
                text=str(message["content"]),
            )
        for index, native_call in enumerate(message.get("tool_calls") or []):
            if not isinstance(native_call, dict):
                continue
            function = native_call.get("function") or {}
            call_id = str(native_call.get("id") or f"call_{index}")
            name = str(function.get("name") or "")
            yield ToolStreamEvent(
                ToolStreamEventKind.TOOL_CALL_START,
                call_id=call_id,
                call_index=index,
                tool_name=name,
            )
            yield ToolStreamEvent(
                ToolStreamEventKind.TOOL_CALL_ARGUMENT_DELTA,
                call_id=call_id,
                call_index=index,
                tool_name=name,
                arguments_delta=self._ollama_argument_fragment(function.get("arguments")),
            )
            yield ToolStreamEvent(
                ToolStreamEventKind.TOOL_CALL_COMPLETED,
                call_id=call_id,
                call_index=index,
                tool_name=name,
            )
        usage = _usage_metadata_from_ollama_response(frame)
        if usage is not None:
            yield ToolStreamEvent(
                ToolStreamEventKind.USAGE,
                usage={
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                },
            )
        yield ToolStreamEvent(
            ToolStreamEventKind.ASSISTANT_COMPLETION,
            finish_reason=(
                "tool_calls"
                if message.get("tool_calls")
                else str(frame.get("done_reason") or "stop")
            ),
        )

    def _run_with_num_predict_growth(
        self,
        runner,
        *,
        runner_name: str,
        initial_num_predict: int,
    ) -> dict[str, Any]:
        """Retry a completion with a larger token budget after truncation."""
        num_predict = max(1, int(initial_num_predict))
        last_result: dict[str, Any] = {
            "text": "",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        for attempt in range(self._max_num_predict_retries + 1):
            result = runner(num_predict)
            text = self._strip_visible_think(result.get("text", "")).strip()
            done_reason = str(result.get("done_reason") or "").strip().lower()
            result["text"] = text

            if text:
                last_result = result

            if done_reason != "length":
                return result

            if attempt >= self._max_num_predict_retries:
                return last_result

            next_num_predict = self._next_num_predict(num_predict)
            self.logger.log_info(
                f"↩️ Retrying {runner_name} after truncated response "
                f"(done=length): num_predict {num_predict} -> {next_num_predict}"
            )
            num_predict = next_num_predict

        return last_result

    # ---------- public API ----------

    def list_models(self):
        """List available models from Ollama."""
        response = requests.get(
            f"{self.service_url}/api/tags",
            timeout=(self._connect_timeout, self._read_timeout),
        )
        response.raise_for_status()
        return [
            model.get("name")
            for model in response.json().get("models", [])
            if isinstance(model.get("name"), str) and model.get("name").strip()
        ]

    def list_model_details(self) -> list[dict[str, Any]]:
        """List available Ollama models with backend size metadata."""
        response = requests.get(
            f"{self.service_url}/api/tags",
            timeout=(self._connect_timeout, self._read_timeout),
        )
        response.raise_for_status()
        models: list[dict[str, Any]] = []

        for item in response.json().get("models", []):
            if not isinstance(item, dict):
                continue

            name = str(item.get("name") or "").strip()
            if not name:
                continue

            details = item.get("details") if isinstance(item.get("details"), dict) else {}
            size_bytes = item.get("size_bytes", item.get("size"))
            size_mb = item.get("size_mb")
            if size_mb in (None, "") and size_bytes not in (None, ""):
                try:
                    size_mb = int(round(float(size_bytes) / (1024.0 * 1024.0)))
                except Exception:
                    size_mb = None
            elif size_mb not in (None, ""):
                try:
                    size_mb = int(round(float(size_mb)))
                except Exception:
                    size_mb = None

            parameter_size = item.get("parameter_size") or details.get("parameter_size")
            quantization_level = item.get("quantization_level") or details.get("quantization_level")
            models.append(
                {
                    "name": name,
                    "digest": item.get("digest"),
                    "size_bytes": size_bytes,
                    "size_mb": size_mb,
                    "parameter_size": parameter_size,
                    "quantization_level": quantization_level,
                }
            )

        return models

    def model_runtime_details(self, model_name: str) -> dict[str, Any]:
        """Return structured Ollama metadata for one exact installed model."""
        response = requests.post(
            f"{self.service_url}/api/show",
            json={"model": str(model_name).strip(), "verbose": False},
            timeout=(self._connect_timeout, self._read_timeout),
        )
        response.raise_for_status()
        payload = response.json()
        model_info = payload.get("model_info")
        info = model_info if isinstance(model_info, dict) else {}
        context_values: list[int] = []
        for key, value in info.items():
            if not str(key).lower().endswith(".context_length"):
                continue
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                context_values.append(parsed)
        parameters = payload.get("parameters")
        configured_runtime_context: int | None = None
        if isinstance(parameters, str):
            configured_context = re.search(
                r"(?m)^num_ctx\s+([1-9][0-9]*)\s*$",
                parameters,
            )
            if configured_context is not None:
                configured_runtime_context = int(configured_context.group(1))
        capabilities = payload.get("capabilities")
        return {
            "provider_declared_context_tokens": (
                min(context_values) if context_values else None
            ),
            "runtime_execution_context_tokens": configured_runtime_context,
            "provider_declared_capabilities": (
                sorted(str(item) for item in capabilities)
                if isinstance(capabilities, list)
                else []
            ),
            "provider_minimum_version": str(payload.get("requires") or "") or None,
        }

    def runtime_context_observation(self) -> RuntimeContextObservation:
        """Observe Ollama's active/model context allocation for this model."""
        details = self.model_runtime_details(self.model_name)
        limit = _coerce_int(details.get("runtime_execution_context_tokens"))
        safe_metadata = {
            "context_limit_tokens": limit,
            "minimum_version": details.get("provider_minimum_version"),
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                safe_metadata,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return RuntimeContextObservation(
            context_limit_tokens=limit if limit and limit > 0 else None,
            source_code="OLLAMA_SHOW",
            observation_fingerprint=fingerprint,
            source_version=str(details.get("provider_minimum_version") or "") or None,
            can_reliably_reread=True,
        )

    def provider_context_serialization(
        self,
        *,
        prompt: str | None = None,
        messages: Sequence[Mapping[str, Any]] | None = None,
        tools: Sequence[Mapping[str, Any]] | None = None,
    ) -> tuple[str, str]:
        """Serialize Ollama's native context-bearing messages and tool schema."""
        if prompt is not None and messages is not None:
            raise ValueError("prompt and messages are mutually exclusive")
        if prompt is None and messages is None:
            raise ValueError("prompt or messages is required")
        if messages is not None:
            native_messages = self._ollama_tool_messages(messages)
        else:
            value = str(prompt or "")
            native_messages = [{"role": "user", "content": value}]
            system_hint = getattr(self, "system_hint", "")
            if len(value.strip()) > 12 and system_hint:
                native_messages.insert(
                    0,
                    {"role": "system", "content": system_hint},
                )
        context_shape: dict[str, Any] = {"messages": native_messages}
        if tools:
            context_shape["tools"] = [dict(item) for item in tools]
        return (
            json.dumps(
                context_shape,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "OLLAMA_NATIVE_CHAT_CONTEXT_V1",
        )

    def send_prompt(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
        generation_options: dict[str, Any] | None = None,
        invocation_options: StrictModelInvocationOptions | None = None,
    ) -> str:
        """
        FORCE think=False (hide visible chain-of-thought). For very short prompts (like "Hi"),
        avoid a system prompt to match the working curl. Retry with larger budget, then fall back
        to /api/generate. Always return non-empty text.
        """
        # Heuristic: for very short inputs, match your curl exactly (no system message)
        p = (prompt or "").strip()
        is_very_short = len(p) <= 12  # "Hi", "Hello", etc.

        if invocation_options is not None:
            strict_options = strict_generation_options(
                generation_options,
                invocation_options,
            )
            result = self._run_strict_pre_output(
                lambda: self._chat_once(
                    p,
                    show_reasoning=False,
                    num_predict=invocation_options.max_output_tokens,
                    use_system=not is_very_short,
                    generation_options=strict_options,
                ),
                invocation_options=invocation_options,
            )
            return str(result.get("text") or "").strip()

        result = self._run_with_num_predict_growth(
            lambda num_predict: self._chat_once(
                p,
                show_reasoning=False,
                num_predict=num_predict,
                use_system=not is_very_short,
                generation_options=generation_options,
            ),
            runner_name="/api/chat",
            initial_num_predict=self._initial_num_predict(generation_options),
        )
        text = str(result.get("text") or "").strip()
        if text:
            return text

        # Fallback: /api/generate with the same truncation-aware budget growth.
        result = self._run_with_num_predict_growth(
            lambda num_predict: self._generate_once(
                p or "Say hi",
                num_predict=num_predict,
                generation_options=generation_options,
            ),
            runner_name="/api/generate",
            initial_num_predict=self._initial_num_predict(generation_options),
        )
        text = str(result.get("text") or "").strip()
        if text:
            return text

        # Absolute last resort: avoid empty payload to server
        return "Hello! 👋"

    def stream_prompt_deltas(
        self,
        prompt_type: str,
        prompt: str,
        generation_options: dict[str, Any] | None = None,
        on_usage_metadata: LLMUsageMetadataCallback | None = None,
        invocation_options: StrictModelInvocationOptions | None = None,
    ) -> Iterator[str]:
        """Yield Ollama response text deltas using native HTTP streaming."""
        del prompt_type
        p = (prompt or "").strip()
        is_very_short = len(p) <= 12
        yielded = False

        if invocation_options is not None:
            strict_options = strict_generation_options(
                generation_options,
                invocation_options,
            )
            attempts = 0
            while True:
                emitted_this_attempt = False
                try:
                    for delta in self._chat_stream(
                        p,
                        show_reasoning=False,
                        num_predict=invocation_options.max_output_tokens,
                        use_system=not is_very_short,
                        generation_options=strict_options,
                        on_usage_metadata=on_usage_metadata,
                    ):
                        emitted_this_attempt = True
                        yielded = True
                        yield delta
                    return
                except (requests.RequestException, TimeoutError):
                    if emitted_this_attempt:
                        raise
                    if attempts >= invocation_options.maximum_pre_output_retries:
                        raise
                    attempts += 1

        for delta in self._chat_stream(
            p,
            show_reasoning=False,
            num_predict=self._initial_num_predict(generation_options),
            use_system=not is_very_short,
            generation_options=generation_options,
            on_usage_metadata=on_usage_metadata,
        ):
            yielded = True
            yield delta

        if not yielded:
            result = self.send_prompt_with_meta(
                prompt_type="U",
                prompt=p,
                stream=False,
                generation_options=generation_options,
            )
            usage = _usage_metadata_from_result(result)
            if usage is not None and on_usage_metadata is not None:
                on_usage_metadata(usage)
            text = result.get("text", "")
            if text:
                yield text

    def send_prompt_with_meta(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
        generation_options: dict[str, Any] | None = None,
        invocation_options: StrictModelInvocationOptions | None = None,
    ) -> dict[str, Any]:
        """
        Send prompt to Ollama and return text plus token metadata.

        Token counts use Ollama's prompt/eval counts. The returned total is
        stored against the assistant turn for dashboard trending.
        """
        p = (prompt or "").strip()
        is_very_short = len(p) <= 12

        if invocation_options is not None:
            strict_options = strict_generation_options(
                generation_options,
                invocation_options,
            )
            result = self._run_strict_pre_output(
                lambda: self._chat_once(
                    p,
                    show_reasoning=False,
                    num_predict=invocation_options.max_output_tokens,
                    use_system=not is_very_short,
                    generation_options=strict_options,
                ),
                invocation_options=invocation_options,
            )
            return {
                "text": str(result.get("text") or "").strip(),
                "done_reason": str(result.get("done_reason") or ""),
                "prompt_tokens": int(result.get("prompt_tokens") or 0),
                "completion_tokens": int(result.get("completion_tokens") or 0),
                "total_tokens": int(result.get("total_tokens") or 0),
            }

        result = self._run_with_num_predict_growth(
            lambda num_predict: self._chat_once(
                p,
                show_reasoning=False,
                num_predict=num_predict,
                use_system=not is_very_short,
                generation_options=generation_options,
            ),
            runner_name="/api/chat",
            initial_num_predict=self._initial_num_predict(generation_options),
        )
        text = str(result.get("text") or "").strip()
        if not text:
            result = self._run_with_num_predict_growth(
                lambda num_predict: self._generate_once(
                    p or "Say hi",
                    num_predict=num_predict,
                    generation_options=generation_options,
                ),
                runner_name="/api/generate",
                initial_num_predict=self._initial_num_predict(generation_options),
            )
            text = str(result.get("text") or "").strip()

        if not text:
            text = "Hello! 👋"

        return {
            "text": text,
            "done_reason": str(result.get("done_reason") or ""),
            "prompt_tokens": int(result.get("prompt_tokens") or 0),
            "completion_tokens": int(result.get("completion_tokens") or 0),
            "total_tokens": int(result.get("total_tokens") or 0),
        }

    @staticmethod
    def _run_strict_pre_output(
        runner: Callable[[], dict[str, Any]],
        *,
        invocation_options: StrictModelInvocationOptions,
    ) -> dict[str, Any]:
        """Retry only transient failures that occur before any response exists."""
        attempts = 0
        while True:
            try:
                return runner()
            except (requests.RequestException, TimeoutError):
                if attempts >= invocation_options.maximum_pre_output_retries:
                    raise
                attempts += 1
