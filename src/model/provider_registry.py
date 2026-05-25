"""Provider registry and capability model for Orac LLM backends."""
# Author: Clive Bostock
# Date: 2026-05-25
# Description: Owns LLM provider mapping, capabilities, and provider-specific
#   model availability checks.

from __future__ import annotations

from dataclasses import dataclass
import subprocess
from typing import Any

import requests

from lib.icons import Icons
from model.llm_connector import LMStudioConnector, OllamaConnector


@dataclass(frozen=True)
class ProviderCapabilities:
    """Describes behaviour exposed by an LLM provider adapter."""

    provider_id: str
    display_name: str
    supports_native_streaming: bool
    uses_fallback_streaming: bool
    supports_usage_metadata: bool
    supports_model_listing: bool
    supports_model_details: bool
    supports_model_pull: bool
    requires_loaded_model: bool
    cancellation_semantics: str


class ProviderRegistry:
    """Factory and provider-owned behaviour registry for LLM connectors."""

    _PROVIDERS: dict[str, tuple[type, ProviderCapabilities]] = {
        "ollama": (
            OllamaConnector,
            ProviderCapabilities(
                provider_id="ollama",
                display_name="Ollama",
                supports_native_streaming=True,
                uses_fallback_streaming=False,
                supports_usage_metadata=True,
                supports_model_listing=True,
                supports_model_details=True,
                supports_model_pull=True,
                requires_loaded_model=False,
                cancellation_semantics="client_disconnect_stops_stream_consumer",
            ),
        ),
        "lmstudio": (
            LMStudioConnector,
            ProviderCapabilities(
                provider_id="lmstudio",
                display_name="LM Studio",
                supports_native_streaming=False,
                uses_fallback_streaming=True,
                supports_usage_metadata=True,
                supports_model_listing=True,
                supports_model_details=False,
                supports_model_pull=False,
                requires_loaded_model=True,
                cancellation_semantics="fallback_non_streaming_call_cannot_be_cancelled_mid_generation",
            ),
        ),
    }

    def __init__(self, *, logger: Any | None = None) -> None:
        self._logger = logger

    def provider_ids(self) -> tuple[str, ...]:
        """Return supported provider identifiers."""
        return tuple(sorted(self._PROVIDERS))

    def capabilities(self, provider_id: str) -> ProviderCapabilities:
        """Return explicit capabilities for a known provider."""
        provider_key = self._normalise_provider_id(provider_id)
        try:
            return self._PROVIDERS[provider_key][1]
        except KeyError as exc:
            raise ValueError(f"Unsupported LLM provider: {provider_id}") from exc

    def connector_class(self, provider_id: str) -> type:
        """Return the connector class for a known provider."""
        provider_key = self._normalise_provider_id(provider_id)
        try:
            return self._PROVIDERS[provider_key][0]
        except KeyError as exc:
            raise ValueError(f"Unsupported LLM provider: {provider_id}") from exc

    def create_connector(
        self,
        *,
        provider_id: str,
        service_url: str,
        model_name: str,
    ) -> Any:
        """Instantiate the connector for a known provider."""
        connector_cls = self.connector_class(provider_id)
        return connector_cls(service_url=service_url, model_name=model_name)

    def validate_or_prepare_model(
        self,
        *,
        provider_id: str,
        service_url: str,
        model_name: str,
    ) -> None:
        """Validate the configured model and perform provider-owned preparation."""
        provider_key = self._normalise_provider_id(provider_id)
        if provider_key == "ollama":
            self._validate_or_pull_ollama_model(model_name=model_name)
            return
        if provider_key == "lmstudio":
            self._validate_lmstudio_model_loaded(
                service_url=service_url,
                model_name=model_name,
            )
            return
        raise RuntimeError(f"{Icons.error} Unknown LLM service: {provider_id}")

    def model_lookup_candidates(
        self,
        *,
        provider_id: str,
        model_name: str,
    ) -> list[str]:
        """Return provider-owned model-name candidates for registry lookup."""
        provider_key = self._normalise_provider_id(provider_id)
        configured_model = str(model_name or "").strip()
        if not configured_model:
            return []

        candidates = [configured_model]
        if provider_key == "ollama":
            if ":" not in configured_model:
                candidates.append(f"{configured_model}:latest")
            elif configured_model.endswith(":latest"):
                candidates.append(configured_model[: -len(":latest")])

        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.add(candidate)
                deduped.append(candidate)
        return deduped

    def backend_model_available(
        self,
        *,
        active_provider_id: str,
        provider_id: str,
        model_name: str,
        available_models: set[str],
        configured_model_name: str,
    ) -> bool:
        """Return whether a selected model is available on the active backend."""
        provider_norm = self._normalise_provider_id(provider_id)
        active_provider_norm = self._normalise_provider_id(active_provider_id)
        model_norm = str(model_name or "").strip()
        if not provider_norm or not model_norm:
            return False
        if provider_norm != active_provider_norm:
            return False
        if model_norm in available_models:
            return True
        return model_norm == str(configured_model_name or "").strip()

    def _validate_or_pull_ollama_model(self, *, model_name: str) -> None:
        """Validate or pull an Ollama model using existing CLI behaviour."""
        try:
            output = subprocess.check_output(["ollama", "list"], text=True)
            if model_name not in output:
                self._log_warning(
                    f"{Icons.warn} Model '{model_name}' not found in Ollama. Pulling it now..."
                )
                subprocess.run(["ollama", "pull", model_name], check=True)
                self._log_info(f"{Icons.tick} Model '{model_name}' pulled successfully.")
            else:
                self._log_info(f"{Icons.tick} Model '{model_name}' is already available in Ollama.")
        except FileNotFoundError as exc:
            self._log_error(f"{Icons.error} Ollama not installed or not in PATH: {exc}")
            raise RuntimeError("Ollama is not installed or not in PATH.") from exc
        except subprocess.CalledProcessError as exc:
            self._log_error(f"{Icons.error} Failed to pull model '{model_name}': {exc}")
            raise RuntimeError(f"Failed to pull model '{model_name}': {exc}") from exc

    def _validate_lmstudio_model_loaded(
        self,
        *,
        service_url: str,
        model_name: str,
    ) -> None:
        """Validate that LM Studio has the configured model loaded."""
        try:
            response = requests.get(f"{service_url}/v1/models", timeout=10)
            response.raise_for_status()
            models = response.json().get("data", [])
            available_models = [model["id"] for model in models]
            if model_name not in available_models:
                message = (
                    f"{Icons.error} Model '{model_name}' not loaded in LM Studio at {service_url}."
                    f"\n{Icons.right_arrow} Please load it in LM Studio and try again."
                )
                self._log_error(message)
                raise RuntimeError(message)
            self._log_info(f"{Icons.tick} Model '{model_name}' is loaded in LM Studio.")
        except requests.exceptions.ConnectionError as exc:
            self._log_error(
                f"{Icons.error} Could not connect to LM Studio server at {service_url}: {exc}"
            )
            raise RuntimeError(f"Could not connect to LM Studio server at {service_url}.") from exc
        except Exception as exc:
            self._log_error(f"{Icons.error} Error validating model in LM Studio: {exc}")
            raise RuntimeError(f"Error validating model in LM Studio: {exc}") from exc

    @staticmethod
    def _normalise_provider_id(provider_id: str) -> str:
        return str(provider_id or "").strip().lower()

    def _log_info(self, message: str) -> None:
        if self._logger is not None:
            self._logger.log_info(message)

    def _log_warning(self, message: str) -> None:
        if self._logger is not None:
            self._logger.log_warning(message)

    def _log_error(self, message: str) -> None:
        if self._logger is not None:
            self._logger.log_error(message)
