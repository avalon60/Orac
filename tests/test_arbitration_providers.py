"""Tests for arbitration configuration and provider adapters."""

# Author: Clive Bostock
# Date: 20-Sep-2026
# Description: Verifies provider independence, schemas, and safe failures.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from types import SimpleNamespace

import httpx
from openai import APIConnectionError, APITimeoutError, NotFoundError
import pytest
import requests

import model.arbitration_provider as provider_module
from model.arbitration_configuration import ArbitrationConfiguration
from model.arbitration_configuration import ArbitrationConfigurationError
from model.arbitration_provider import ArbitrationProviderError
from model.arbitration_provider import OllamaArbitrationProvider
from model.arbitration_provider import OpenAICompatibleArbitrationProvider
from model.arbitration_provider import create_arbitration_provider
from model.arbitration_provider import initialise_arbitration


class _Config:
    """Minimal ConfigManager-compatible test adapter."""

    def __init__(self, values):
        self.values = values

    def bool_config_value(self, section, key, default=None):
        value = self.values.get((section, key), default)
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"true", "yes", "1", "on"}

    def config_value(self, section, key, default=None):
        return self.values.get((section, key), default)


def test_disabled_configuration_does_not_require_provider_properties() -> None:
    config = ArbitrationConfiguration.from_config(_Config({}))
    assert config == ArbitrationConfiguration(enabled=False)


@pytest.mark.parametrize("field", ["provider", "model", "endpoint"])
def test_enabled_configuration_rejects_missing_required_http_fields(field) -> None:
    values = {
        ("arbitrator", "enabled"): True,
        ("arbitrator", "provider"): "ollama",
        ("arbitrator", "model"): "router",
        ("arbitrator", "endpoint"): "http://localhost:11434",
    }
    values[("arbitrator", field)] = ""
    with pytest.raises(ArbitrationConfigurationError):
        ArbitrationConfiguration.from_config(_Config(values))


def test_arbitrator_configuration_is_independent_from_main_model() -> None:
    values = {
        ("arbitrator", "enabled"): True,
        ("arbitrator", "provider"): "ollama",
        ("arbitrator", "model"): "same-model",
        ("arbitrator", "endpoint"): "http://localhost:11434",
        ("service", "default_model_name"): "same-model",
    }
    config = ArbitrationConfiguration.from_config(_Config(values))
    assert config.model == "same-model"
    assert not hasattr(config, "use_main_model")


def test_ollama_uses_native_schema_and_bounded_stateless_chat(monkeypatch) -> None:
    captured = {}

    class _Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": "{}"}}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return _Response()

    monkeypatch.setattr(provider_module.requests, "post", fake_post)
    config = ArbitrationConfiguration(
        enabled=True,
        provider="ollama",
        model="router",
        endpoint="http://localhost:11434",
        timeout_seconds=3,
    )
    result = OllamaArbitrationProvider(config).complete(
        messages=({"role": "user", "content": "x"},),
        response_schema={"type": "object"},
    )
    assert result == "{}"
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["json"]["format"] == {"type": "object"}
    assert captured["json"]["stream"] is False
    assert captured["json"]["options"]["num_predict"] == 256


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (requests.Timeout(), "timeout"),
        (requests.ConnectionError(), "connection_failure"),
    ],
)
def test_ollama_normalises_transport_failures(monkeypatch, error, code) -> None:
    monkeypatch.setattr(
        provider_module.requests,
        "post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )
    provider = OllamaArbitrationProvider(
        ArbitrationConfiguration(
            enabled=True,
            provider="ollama",
            model="router",
            endpoint="http://localhost:11434",
        )
    )
    with pytest.raises(ArbitrationProviderError, match=code):
        provider.complete(messages=(), response_schema={})


def test_openai_compatible_preserves_endpoint_and_binds_schema(monkeypatch) -> None:
    captured = {}

    class _Runnable:
        def invoke(self, messages):
            captured["messages"] = messages
            return SimpleNamespace(content="{}")

    class _Client:
        def __init__(self, **kwargs):
            captured["init"] = kwargs

        def bind(self, **kwargs):
            captured["bind"] = kwargs
            return _Runnable()

    monkeypatch.setattr(provider_module, "ChatOpenAI", _Client)
    provider = OpenAICompatibleArbitrationProvider(
        ArbitrationConfiguration(
            enabled=True,
            provider="openai_compatible",
            model="router",
            endpoint="http://localhost:9000/custom/v1",
            timeout_seconds=2,
        )
    )
    provider.complete(
        messages=({"role": "user", "content": "x"},),
        response_schema={"type": "object"},
    )
    assert captured["init"]["base_url"] == "http://localhost:9000/custom/v1"
    assert captured["init"]["max_retries"] == 0
    assert captured["init"]["max_tokens"] == 256
    assert captured["bind"]["response_format"]["type"] == "json_schema"


@pytest.mark.parametrize(
    ("sdk_error_factory", "expected_code"),
    [
        (
            lambda request: APITimeoutError(request=request),
            "timeout",
        ),
        (
            lambda request: APIConnectionError(request=request),
            "connection_failure",
        ),
        (
            lambda request: NotFoundError(
                "model missing",
                response=httpx.Response(404, request=request),
                body=None,
            ),
            "model_unavailable",
        ),
    ],
)
def test_openai_compatible_normalises_sdk_failures(
    monkeypatch,
    sdk_error_factory,
    expected_code,
) -> None:
    request = httpx.Request("POST", "http://localhost:9000/v1/chat/completions")

    class _Runnable:
        def invoke(self, _messages):
            raise sdk_error_factory(request)

    class _Client:
        def __init__(self, **_kwargs):
            pass

        def bind(self, **_kwargs):
            return _Runnable()

    monkeypatch.setattr(provider_module, "ChatOpenAI", _Client)
    provider = OpenAICompatibleArbitrationProvider(
        ArbitrationConfiguration(
            enabled=True,
            provider="openai_compatible",
            model="router",
            endpoint="http://localhost:9000/v1",
        )
    )
    with pytest.raises(ArbitrationProviderError, match=expected_code):
        provider.complete(messages=(), response_schema={})


def test_ollama_malformed_envelope_and_missing_model_are_categorised(
    monkeypatch,
) -> None:
    configuration = ArbitrationConfiguration(
        enabled=True,
        provider="ollama",
        model="router",
        endpoint="http://localhost:11434",
    )

    class _MalformedResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": []}

    monkeypatch.setattr(
        provider_module.requests,
        "post",
        lambda *_args, **_kwargs: _MalformedResponse(),
    )
    with pytest.raises(ArbitrationProviderError, match="malformed_envelope"):
        OllamaArbitrationProvider(configuration).complete(
            messages=(), response_schema={}
        )

    response = requests.Response()
    response.status_code = 404
    error = requests.HTTPError(response=response)
    monkeypatch.setattr(
        provider_module.requests,
        "post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )
    with pytest.raises(ArbitrationProviderError, match="model_unavailable"):
        OllamaArbitrationProvider(configuration).complete(
            messages=(), response_schema={}
        )


def test_edge_runtime_is_an_injected_extension_point() -> None:
    sentinel = SimpleNamespace(complete=lambda **_kwargs: {})
    config = ArbitrationConfiguration(
        enabled=True, provider="edge_runtime", model="small-router", endpoint=""
    )
    assert (
        create_arbitration_provider(
            config, edge_runtime_factory=lambda received: sentinel
        )
        is sentinel
    )
    with pytest.raises(ArbitrationProviderError, match="runtime_unavailable"):
        create_arbitration_provider(config)


def test_invalid_enabled_boolean_is_a_clear_configuration_error() -> None:
    class _InvalidBooleanConfig(_Config):
        def bool_config_value(self, section, key, default=None):
            raise ValueError("bad boolean")

    with pytest.raises(ArbitrationConfigurationError, match="enabled"):
        ArbitrationConfiguration.from_config(_InvalidBooleanConfig({}))


@pytest.mark.parametrize(
    ("provider", "endpoint"),
    [
        ("unknown", "http://localhost:1"),
        ("ollama", "localhost:11434"),
        ("openai_compatible", "file:///tmp/model"),
    ],
)
def test_enabled_configuration_rejects_unknown_provider_or_http_endpoint(
    provider,
    endpoint,
) -> None:
    values = {
        ("arbitrator", "enabled"): True,
        ("arbitrator", "provider"): provider,
        ("arbitrator", "model"): "router",
        ("arbitrator", "endpoint"): endpoint,
    }
    with pytest.raises(ArbitrationConfigurationError):
        ArbitrationConfiguration.from_config(_Config(values))


def test_enabled_configuration_rejects_invalid_api_key_environment_name() -> None:
    values = {
        ("arbitrator", "enabled"): True,
        ("arbitrator", "provider"): "openai_compatible",
        ("arbitrator", "model"): "router",
        ("arbitrator", "endpoint"): "http://localhost:9000/v1",
        ("arbitrator", "api_key_env"): "not a variable",
    }
    with pytest.raises(ArbitrationConfigurationError, match="api_key_env"):
        ArbitrationConfiguration.from_config(_Config(values))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("timeout_seconds", "0"),
        ("timeout_seconds", "121"),
        ("timeout_seconds", "nan"),
        ("min_confidence", "-0.1"),
        ("min_confidence", "1.1"),
        ("min_confidence", "inf"),
    ],
)
def test_enabled_configuration_rejects_invalid_numeric_bounds(key, value) -> None:
    values = {
        ("arbitrator", "enabled"): True,
        ("arbitrator", "provider"): "ollama",
        ("arbitrator", "model"): "router",
        ("arbitrator", "endpoint"): "http://localhost:11434",
        ("arbitrator", key): value,
    }
    with pytest.raises(ArbitrationConfigurationError):
        ArbitrationConfiguration.from_config(_Config(values))


def test_unexpected_provider_constructor_failure_is_safely_categorised(
    monkeypatch,
) -> None:
    class _BrokenClient:
        def __init__(self, **_kwargs):
            raise ValueError("raw constructor detail")

    monkeypatch.setattr(provider_module, "ChatOpenAI", _BrokenClient)
    configuration = ArbitrationConfiguration(
        enabled=True,
        provider="openai_compatible",
        model="router",
        endpoint="http://localhost:9000/v1",
    )
    with pytest.raises(
        ArbitrationProviderError,
        match="provider_initialisation_failed",
    ) as captured:
        create_arbitration_provider(configuration)
    assert "raw constructor detail" not in str(captured.value)


def test_unexpected_edge_factory_failure_is_safely_categorised() -> None:
    configuration = ArbitrationConfiguration(
        enabled=True,
        provider="edge_runtime",
        model="router",
    )

    def broken_factory(_configuration):
        raise RuntimeError("vendor runtime secret detail")

    with pytest.raises(
        ArbitrationProviderError,
        match="provider_initialisation_failed",
    ) as captured:
        create_arbitration_provider(
            configuration,
            edge_runtime_factory=broken_factory,
        )
    assert "vendor runtime secret detail" not in str(captured.value)


def test_disabled_runtime_never_constructs_provider() -> None:
    calls = []
    configuration, provider = initialise_arbitration(
        _Config({}),
        provider_factory=lambda config: calls.append(config),
    )
    assert configuration.enabled is False
    assert provider is None
    assert calls == []


def test_enabled_invalid_runtime_returns_conservative_unavailable_provider() -> None:
    values = {
        ("arbitrator", "enabled"): True,
        ("arbitrator", "provider"): "ollama",
        ("arbitrator", "model"): "",
        ("arbitrator", "endpoint"): "http://localhost:11434",
    }
    configuration, provider = initialise_arbitration(_Config(values))
    assert configuration.enabled is True
    with pytest.raises(ArbitrationProviderError, match="invalid_configuration"):
        provider.complete(messages=(), response_schema={})


def test_unexpected_runtime_factory_error_is_contained_without_raw_detail() -> None:
    values = {
        ("arbitrator", "enabled"): True,
        ("arbitrator", "provider"): "ollama",
        ("arbitrator", "model"): "router",
        ("arbitrator", "endpoint"): "http://localhost:11434",
    }

    def broken_factory(_configuration):
        raise RuntimeError("secret construction detail")

    configuration, provider = initialise_arbitration(
        _Config(values),
        provider_factory=broken_factory,
    )
    assert configuration.enabled is True
    with pytest.raises(
        ArbitrationProviderError,
        match="provider_initialisation_failed",
    ) as captured:
        provider.complete(messages=(), response_schema={})
    assert "secret construction detail" not in str(captured.value)
