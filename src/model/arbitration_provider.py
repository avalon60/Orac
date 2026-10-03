"""Provider-neutral model clients for LLM routing arbitration."""

# Author: Clive Bostock
# Date: 20-Sep-2026
# Description: Invokes bounded arbitration requests through supported runtimes.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from collections.abc import Callable, Mapping
import os
from typing import Any, Protocol, cast

from langchain_openai import ChatOpenAI
from openai import APIConnectionError, APITimeoutError, NotFoundError
from pydantic import SecretStr
import requests

from model.arbitration_configuration import ArbitrationConfiguration
from model.arbitration_configuration import ArbitrationConfigurationError


class ArbitrationProviderError(RuntimeError):
    """A safe, categorised arbitration provider failure."""

    def __init__(self, code: str) -> None:
        """Initialise a failure with a non-sensitive diagnostic code."""
        super().__init__(code)
        self.code = code


class ArbitrationProvider(Protocol):
    """Small provider contract used by the routing adviser."""

    def complete(
        self,
        *,
        messages: tuple[Mapping[str, str], ...],
        response_schema: Mapping[str, Any],
    ) -> str | Mapping[str, Any]:
        """Return one structured arbitration response."""
        ...


EdgeRuntimeFactory = Callable[[ArbitrationConfiguration], ArbitrationProvider]
ArbitrationProviderFactory = Callable[[ArbitrationConfiguration], ArbitrationProvider]


class UnavailableArbitrationProvider:
    """Preserve safe enabled-mode fallback when a provider cannot initialise."""

    def __init__(self, code: str) -> None:
        """Initialise the provider with a safe diagnostic category."""
        self._code = code

    def complete(
        self,
        *,
        messages: tuple[Mapping[str, str], ...],
        response_schema: Mapping[str, Any],
    ) -> str | Mapping[str, Any]:
        """Fail without contacting a runtime or accepting weak interception."""
        raise ArbitrationProviderError(self._code)


class OllamaArbitrationProvider:
    """Invoke an Ollama model with native JSON-schema output constraints."""

    def __init__(self, configuration: ArbitrationConfiguration) -> None:
        """Initialise the client without loading or pulling a model."""
        self._configuration = configuration

    def complete(
        self,
        *,
        messages: tuple[Mapping[str, str], ...],
        response_schema: Mapping[str, Any],
    ) -> str | Mapping[str, Any]:
        """Invoke Ollama's stateless chat API."""
        payload = {
            "model": self._configuration.model,
            "messages": [dict(message) for message in messages],
            "stream": False,
            "think": False,
            "format": dict(response_schema),
            "options": {"temperature": 0, "num_predict": 256},
        }
        try:
            response = requests.post(
                self._configuration.endpoint.rstrip("/") + "/api/chat",
                json=payload,
                timeout=(
                    min(5.0, self._configuration.timeout_seconds),
                    self._configuration.timeout_seconds,
                ),
            )
            response.raise_for_status()
            body = response.json()
        except requests.Timeout as exc:
            raise ArbitrationProviderError("timeout") from exc
        except requests.ConnectionError as exc:
            raise ArbitrationProviderError("connection_failure") from exc
        except requests.HTTPError as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            code = "model_unavailable" if status_code == 404 else "provider_error"
            raise ArbitrationProviderError(code) from exc
        except requests.RequestException as exc:
            raise ArbitrationProviderError("provider_error") from exc
        except (TypeError, ValueError) as exc:
            raise ArbitrationProviderError("malformed_envelope") from exc
        if not isinstance(body, Mapping) or not isinstance(
            body.get("message"), Mapping
        ):
            raise ArbitrationProviderError("malformed_envelope")
        content = body["message"].get("content")
        if not isinstance(content, str):
            raise ArbitrationProviderError("malformed_envelope")
        return content


class OpenAICompatibleArbitrationProvider:
    """Invoke an OpenAI-compatible endpoint using the shared client stack."""

    def __init__(self, configuration: ArbitrationConfiguration) -> None:
        """Initialise the protocol-compatible client at the exact endpoint."""
        api_key = "not-needed"
        if configuration.api_key_env:
            api_key = os.environ.get(configuration.api_key_env, "")
            if not api_key:
                raise ArbitrationProviderError("missing_api_key")
        self._client = ChatOpenAI(
            base_url=configuration.endpoint.rstrip("/"),
            api_key=cast(SecretStr, api_key),
            model=configuration.model,
            temperature=0,
            timeout=configuration.timeout_seconds,
            max_retries=0,
            max_tokens=256,
        )

    def complete(
        self,
        *,
        messages: tuple[Mapping[str, str], ...],
        response_schema: Mapping[str, Any],
    ) -> str | Mapping[str, Any]:
        """Invoke a strict JSON-schema completion without prose parsing."""
        try:
            runnable = self._client.bind(
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "orac_routing_decision",
                        "strict": True,
                        "schema": dict(response_schema),
                    },
                }
            )
            result = runnable.invoke([dict(message) for message in messages])
        except APITimeoutError as exc:
            raise ArbitrationProviderError("timeout") from exc
        except APIConnectionError as exc:
            raise ArbitrationProviderError("connection_failure") from exc
        except NotFoundError as exc:
            raise ArbitrationProviderError("model_unavailable") from exc
        except Exception as exc:
            raise ArbitrationProviderError("provider_error") from exc
        content = getattr(result, "content", None)
        if not isinstance(content, (str, Mapping)):
            raise ArbitrationProviderError("malformed_envelope")
        return content


def create_arbitration_provider(
    configuration: ArbitrationConfiguration,
    *,
    edge_runtime_factory: EdgeRuntimeFactory | None = None,
) -> ArbitrationProvider:
    """Create a configured provider without coupling decision logic to hosting."""
    try:
        if configuration.provider == "ollama":
            return OllamaArbitrationProvider(configuration)
        if configuration.provider == "openai_compatible":
            return OpenAICompatibleArbitrationProvider(configuration)
        if configuration.provider == "edge_runtime":
            if edge_runtime_factory is None:
                raise ArbitrationProviderError("runtime_unavailable")
            return edge_runtime_factory(configuration)
        raise ArbitrationProviderError("unsupported_provider")
    except ArbitrationProviderError:
        raise
    except Exception as exc:
        raise ArbitrationProviderError("provider_initialisation_failed") from exc


def initialise_arbitration(
    config_mgr: Any,
    *,
    logger: Any | None = None,
    provider_factory: ArbitrationProviderFactory | None = None,
) -> tuple[ArbitrationConfiguration, ArbitrationProvider | None]:
    """Build optional arbitration without allowing startup failures to escape.

    Disabled configuration never constructs a provider. Enabled but invalid or
    unavailable configuration returns a provider that always fails closed into
    the normal conversational fallback, preventing legacy embedding-only
    interception from being restored by a provider outage.
    """
    factory = provider_factory or create_arbitration_provider
    try:
        requested = bool(
            config_mgr.bool_config_value("arbitrator", "enabled", default=False)
        )
    except (TypeError, ValueError):
        requested = True
    configuration = ArbitrationConfiguration(enabled=requested)
    try:
        configuration = ArbitrationConfiguration.from_config(config_mgr)
        if not configuration.enabled:
            _provider_log(logger, "debug", "LLM routing arbitration is disabled.")
            return configuration, None
        provider = factory(configuration)
        _provider_log(
            logger,
            "info",
            "LLM routing arbitration enabled: "
            f"provider={configuration.provider} model={configuration.model}",
        )
        return configuration, provider
    except ArbitrationConfigurationError:
        code = "invalid_configuration"
    except ArbitrationProviderError as exc:
        code = exc.code
    except Exception:
        code = "provider_initialisation_failed"

    _provider_log(
        logger,
        "warning",
        "LLM routing arbitration unavailable; deterministic routing continues: "
        f"reason={code}",
    )
    if configuration.enabled:
        return configuration, UnavailableArbitrationProvider(code)
    return configuration, None


def _provider_log(logger: Any | None, level: str, message: str) -> None:
    """Write a safe provider lifecycle diagnostic when a logger is available."""
    method = getattr(logger, f"log_{level}", None)
    if callable(method):
        method(message)
