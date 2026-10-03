"""Protocol translation for the Orac Gateway HTTP service."""
# Author: Clive Bostock
# Date: 28-Sep-2026
# Description: Maps OpenAI and Ollama wire contracts to the canonical Core processor.

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
import json
import time
from typing import Any, Callable

from orac_core.communications import CapabilityRestrictions
from orac_core.communications import ConversationContext
from orac_core.communications import PrincipalContext
from orac_core.communications.adapters.openai import OpenAIAdapter
from orac_core.communications.adapters.openai import OpenAIAdapterError
from orac_core.communications.adapters.openai import serialise_models

from .auth import GatewayIdentity


class GatewayProtocolError(ValueError):
    """Represent a safe HTTP protocol failure."""

    def __init__(self, status: int, code: str, message: str) -> None:
        """Initialise status, stable code, and safe message."""
        super().__init__(message)
        self.status = status
        self.code = code


class GatewayProtocol:
    """Expose both wire protocols through one canonical communications gate."""

    def __init__(
        self,
        *,
        processor: Any,
        model_catalog_provider: Callable[[], list[dict[str, Any]]],
        embedding_provider: Callable[[str, list[str]], list[list[float]]] | None,
    ) -> None:
        """Initialise the facade with narrow host-owned collaborators."""
        self._openai = OpenAIAdapter(processor)
        self._processor = processor
        self._models = model_catalog_provider
        self._embed = embedding_provider

    def openai_models(self, identity: GatewayIdentity) -> dict[str, Any]:
        """Return the authorised model catalogue in OpenAI form."""
        return serialise_models(self._authorised_models(identity))

    def ollama_tags(self, identity: GatewayIdentity) -> dict[str, Any]:
        """Return the authorised model catalogue in Ollama form."""
        return {
            "models": [
                {
                    "name": model["id"],
                    "model": model["id"],
                    "modified_at": "1970-01-01T00:00:00Z",
                    "size": 0,
                    "digest": "",
                    "details": {},
                }
                for model in self._authorised_models(identity)
            ]
        }

    async def openai_chat(
        self,
        payload: Mapping[str, Any],
        identity: GatewayIdentity,
        context: ConversationContext,
    ) -> dict[str, Any]:
        """Run one non-streaming OpenAI Chat Completions request."""
        try:
            return await self._openai.chat_completions(
                payload,
                self._principal(identity),
                context,
                restrictions=self._restrictions(identity),
            )
        except OpenAIAdapterError as exc:
            raise GatewayProtocolError(400, exc.code, str(exc)) from exc

    def validate_openai_chat(
        self,
        payload: Mapping[str, Any],
        identity: GatewayIdentity,
        context: ConversationContext,
    ) -> None:
        """Validate a streaming request before HTTP response headers are sent."""
        try:
            self._openai.to_request(
                payload,
                principal=self._principal(identity),
                context=context,
                restrictions=self._restrictions(identity),
            )
        except OpenAIAdapterError as exc:
            raise GatewayProtocolError(400, exc.code, str(exc)) from exc

    def validate_ollama_chat(
        self,
        payload: Mapping[str, Any],
        identity: GatewayIdentity,
        context: ConversationContext,
    ) -> None:
        """Validate an Ollama stream before HTTP response headers are sent."""
        translated = _ollama_to_openai(payload)
        self.validate_openai_chat(translated, identity, context)

    async def stream_openai_chat(
        self,
        payload: Mapping[str, Any],
        identity: GatewayIdentity,
        context: ConversationContext,
    ) -> AsyncIterator[bytes]:
        """Yield OpenAI SSE frames without response buffering."""
        try:
            stream = self._openai.stream_chat_completions(
                payload,
                self._principal(identity),
                context,
                restrictions=self._restrictions(identity),
            )
            async for frame in stream:
                yield frame.encode("utf-8")
        except OpenAIAdapterError as exc:
            raise GatewayProtocolError(400, exc.code, str(exc)) from exc

    async def ollama_chat(
        self,
        payload: Mapping[str, Any],
        identity: GatewayIdentity,
        context: ConversationContext,
    ) -> dict[str, Any]:
        """Run one non-streaming Ollama-native chat request."""
        translated = _ollama_to_openai(payload)
        result = await self.openai_chat(translated, identity, context)
        if "error" in result:
            return result
        choice = result["choices"][0]
        return {
            "model": result.get("model"),
            "created_at": _ollama_timestamp(),
            "message": choice["message"],
            "done": True,
            "done_reason": choice.get("finish_reason") or "stop",
            "prompt_eval_count": result.get("usage", {}).get("prompt_tokens", 0),
            "eval_count": result.get("usage", {}).get("completion_tokens", 0),
        }

    async def stream_ollama_chat(
        self,
        payload: Mapping[str, Any],
        identity: GatewayIdentity,
        context: ConversationContext,
    ) -> AsyncIterator[bytes]:
        """Yield Ollama newline-delimited JSON from canonical stream events."""
        translated = _ollama_to_openai(payload)
        request = self._openai.to_request(
            translated,
            principal=self._principal(identity),
            context=context,
            restrictions=self._restrictions(identity),
        )
        async for event in self._processor.stream(request):
            if event.kind.value == "text_delta" and event.delta:
                item = {
                    "model": request.model,
                    "created_at": _ollama_timestamp(),
                    "message": {"role": "assistant", "content": event.delta},
                    "done": False,
                }
                yield _ndjson(item)
            elif event.kind.value == "error" and event.error is not None:
                yield _ndjson({"error": event.error.message, "done": True})
            elif event.kind.value == "complete":
                result = event.result
                item = {
                    "model": result.model if result is not None else request.model,
                    "created_at": _ollama_timestamp(),
                    "message": {"role": "assistant", "content": ""},
                    "done": True,
                    "done_reason": (
                        result.finish_reason if result is not None else "stop"
                    ),
                }
                if result is not None and result.usage is not None:
                    item["prompt_eval_count"] = result.usage.prompt_tokens
                    item["eval_count"] = result.usage.completion_tokens
                yield _ndjson(item)

    def embeddings(
        self,
        payload: Mapping[str, Any],
        identity: GatewayIdentity,
        *,
        ollama: bool,
    ) -> dict[str, Any]:
        """Return authorised embeddings in the requested wire format."""
        if self._embed is None:
            raise GatewayProtocolError(501, "not_implemented", "Embeddings are unavailable.")
        model = str(payload.get("model") or "").strip()
        if not model:
            raise GatewayProtocolError(400, "invalid_request_error", "Model is required.")
        if identity.allowed_models is not None and model not in identity.allowed_models:
            raise GatewayProtocolError(403, "model_not_authorised", "Model is not authorised.")
        value = payload.get("input")
        if isinstance(value, str):
            inputs = [value]
        elif isinstance(value, list) and value and all(isinstance(item, str) for item in value):
            inputs = list(value)
        else:
            raise GatewayProtocolError(
                400, "invalid_request_error", "Input must be text or a non-empty text array."
            )
        if len(inputs) > 64 or sum(len(item) for item in inputs) > 262144:
            raise GatewayProtocolError(413, "request_too_large", "Embedding input is too large.")
        try:
            vectors = self._embed(model, inputs)
        except ValueError as exc:
            raise GatewayProtocolError(400, "invalid_request_error", str(exc)) from exc
        if ollama:
            return {"model": model, "embeddings": vectors}
        return {
            "object": "list",
            "model": model,
            "data": [
                {"object": "embedding", "index": index, "embedding": vector}
                for index, vector in enumerate(vectors)
            ],
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
        }

    def _authorised_models(self, identity: GatewayIdentity) -> list[dict[str, Any]]:
        """Intersect the Core catalogue with client restrictions."""
        models = self._models()
        if identity.allowed_models is None:
            return models
        return [model for model in models if str(model.get("id")) in identity.allowed_models]

    @staticmethod
    def _principal(identity: GatewayIdentity) -> PrincipalContext:
        return PrincipalContext(identity.principal, host_identity="orac-gateway")

    @staticmethod
    def _restrictions(identity: GatewayIdentity) -> CapabilityRestrictions:
        return CapabilityRestrictions(model_ids=identity.allowed_models)


def _ollama_to_openai(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Translate the supported Ollama chat subset without dropping semantics."""
    supported_fields = {"model", "messages", "stream", "tools", "options", "keep_alive"}
    unknown_fields = sorted(str(key) for key in payload if key not in supported_fields)
    if unknown_fields:
        raise GatewayProtocolError(
            400,
            "unsupported_parameter",
            "Unsupported Ollama chat field(s): " + ", ".join(unknown_fields),
        )
    if payload.get("tools") is not None:
        raise GatewayProtocolError(
            400, "unsupported_parameter", "Client-managed tools are not supported by this gateway version."
        )
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise GatewayProtocolError(400, "invalid_request_error", "Messages are required.")
    for message in messages:
        if not isinstance(message, Mapping):
            raise GatewayProtocolError(400, "invalid_request_error", "Messages must be objects.")
        if message.get("images") or message.get("tool_calls") or message.get("tool_call_id"):
            raise GatewayProtocolError(
                400,
                "unsupported_parameter",
                "Images and client-managed tool transcripts are not supported by this gateway version.",
            )
    result: dict[str, Any] = {
        "model": payload.get("model"),
        "messages": messages,
        "stream": bool(payload.get("stream")),
    }
    metadata: dict[str, Any] = {}
    if payload.get("keep_alive") is not None:
        keep_alive = payload["keep_alive"]
        if not isinstance(keep_alive, (str, int)) or isinstance(keep_alive, bool):
            raise GatewayProtocolError(
                400, "invalid_request_error", "keep_alive must be a duration or integer."
            )
        metadata["requested_keep_alive"] = str(keep_alive)[:64]
    options = payload.get("options")
    if options is not None and not isinstance(options, Mapping):
        raise GatewayProtocolError(400, "invalid_request_error", "Options must be an object.")
    options = options or {}
    supported = {"temperature", "top_p", "seed", "num_predict", "num_ctx"}
    unknown = sorted(str(key) for key in options if key not in supported)
    if unknown:
        raise GatewayProtocolError(
            400, "unsupported_parameter", "Unsupported Ollama option(s): " + ", ".join(unknown)
        )
    for key in ("temperature", "top_p", "seed"):
        if key in options:
            result[key] = options[key]
    if "num_predict" in options:
        result["max_tokens"] = options["num_predict"]
    if "num_ctx" in options:
        num_ctx = options["num_ctx"]
        if isinstance(num_ctx, bool) or not isinstance(num_ctx, int) or num_ctx <= 0:
            raise GatewayProtocolError(
                400, "invalid_request_error", "num_ctx must be a positive integer."
            )
        metadata["requested_context_tokens"] = min(num_ctx, 1048576)
    if metadata:
        result["metadata"] = metadata
    # Core records this client hint but remains authoritative for context budgeting.
    return result


def _ndjson(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(dict(value), ensure_ascii=False) + "\n").encode("utf-8")


def _ollama_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
