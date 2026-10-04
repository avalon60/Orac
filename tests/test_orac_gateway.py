"""Tests for the dual-protocol Orac Gateway plugin."""
# Author: Clive Bostock
# Date: 28-Sep-2026
# Description: Verifies authentication, protocol preservation, and Core delegation.
# ruff: noqa: E402

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import socket
import sys
import threading
import time
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request
from urllib.request import urlopen

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from orac_core.communications import Message
from orac_core.communications import MessageRole
from orac_core.communications import OracResponse
from orac_core.communications import StreamEvent
from orac_core.communications import StreamEventKind
from orac_core.communications import Usage
from plugins.orac_gateway.auth import GatewayAuthenticationError
from plugins.orac_gateway.auth import GatewayAuthenticator
from plugins.orac_gateway.auth import GatewayIdentity
from plugins.orac_gateway.auth import validate_listener_policy
from plugins.orac_gateway.plugin import OracGatewayPlugin
from plugins.orac_gateway.protocol import GatewayProtocol
from plugins.orac_gateway.protocol import GatewayProtocolError
from plugins.orac_gateway.service import OracGatewayService


class _RecordingProcessor:
    """Record canonical requests while returning deterministic responses."""

    def __init__(self) -> None:
        self.requests = []

    async def process(self, request, *, event_sink=None):
        self.requests.append(request)
        return OracResponse(
            request.request_id,
            request.correlation_id,
            "conversation-1",
            request.model,
            Message(MessageRole.ASSISTANT, "grounded answer"),
            "stop",
            Usage(12, 3),
        )

    async def stream(self, request):
        self.requests.append(request)
        yield StreamEvent(
            request.request_id,
            request.correlation_id,
            1,
            StreamEventKind.TEXT_DELTA,
            delta="grounded ",
        )
        response = OracResponse(
            request.request_id,
            request.correlation_id,
            "conversation-1",
            request.model,
            Message(MessageRole.ASSISTANT, "grounded answer"),
            "stop",
            Usage(12, 3),
        )
        yield StreamEvent(
            request.request_id,
            request.correlation_id,
            2,
            StreamEventKind.COMPLETE,
            result=response,
        )


def _protocol(processor=None) -> GatewayProtocol:
    return GatewayProtocol(
        processor=processor or _RecordingProcessor(),
        model_catalog_provider=lambda: [
            {"id": "qwen-local", "owned_by": "orac"},
            {"id": "restricted", "owned_by": "orac"},
        ],
        embedding_provider=lambda model, inputs: [[float(len(value))] for value in inputs],
    )


def test_plugin_entry_point_declines_direct_execution() -> None:
    """The service-only marker must satisfy readiness without a second route."""
    plugin = OracGatewayPlugin()

    assert plugin.execute("hello", {"source": "test"}) is None
    assert plugin.handle(object()) == {
        "status": "unsupported",
        "message": "Orac Gateway is available through its managed HTTP service.",
    }


def test_trusted_loopback_authentication_is_strictly_local() -> None:
    """Trusted mode must never authenticate a non-loopback client."""
    auth = GatewayAuthenticator(mode="trusted_loopback", principal="alice")

    assert auth.authenticate(client_host="127.0.0.1", headers={}).principal == "alice"
    with pytest.raises(GatewayAuthenticationError):
        auth.authenticate(client_host="192.0.2.4", headers={})
    with pytest.raises(ValueError):
        validate_listener_policy("0.0.0.0", "trusted_loopback")


def test_bearer_authentication_uses_host_configured_identity() -> None:
    """Wire credentials should select only the configured server-side identity."""
    auth = GatewayAuthenticator(
        mode="bearer",
        principal="gateway_user",
        bearer_token="secret-token",
        allowed_models=frozenset({"qwen-local"}),
    )

    identity = auth.authenticate(
        client_host="192.0.2.4",
        headers={"Authorization": "Bearer secret-token"},
    )

    assert identity.principal == "gateway_user"
    assert identity.allowed_models == frozenset({"qwen-local"})
    with pytest.raises(GatewayAuthenticationError):
        auth.authenticate(client_host="192.0.2.4", headers={})


def test_model_discovery_intersects_core_catalogue_with_allowlist() -> None:
    """Both protocols should expose the same approved Core catalogue."""
    protocol = _protocol()
    identity = GatewayIdentity("alice", frozenset({"qwen-local"}))

    assert [item["id"] for item in protocol.openai_models(identity)["data"]] == [
        "qwen-local"
    ]
    assert [item["name"] for item in protocol.ollama_tags(identity)["models"]] == [
        "qwen-local"
    ]


def test_openai_chat_delegates_once_and_preserves_generation_controls() -> None:
    """OpenAI chat should enter the Core processor once with bounded controls."""
    processor = _RecordingProcessor()
    protocol = _protocol(processor)
    identity = GatewayIdentity("alice", frozenset({"qwen-local"}))
    payload = {
        "model": "qwen-local",
        "messages": [{"role": "user", "content": "Use Orac evidence"}],
        "temperature": 0.3,
        "top_p": 0.8,
        "max_tokens": 100,
        "seed": 7,
    }

    result = asyncio.run(protocol.openai_chat(payload, identity, None))

    assert result["choices"][0]["message"]["content"] == "grounded answer"
    assert len(processor.requests) == 1
    request = processor.requests[0]
    assert request.principal.username == "alice"
    assert request.restrictions.model_ids == frozenset({"qwen-local"})
    assert dict(request.metadata) | {} == {
        "temperature": 0.3,
        "top_p": 0.8,
        "max_tokens": 100,
        "seed": 7,
    }


def test_ollama_chat_and_ndjson_stream_use_same_core_gate() -> None:
    """The native adapter should project JSON and NDJSON without another runtime."""
    processor = _RecordingProcessor()
    protocol = _protocol(processor)
    identity = GatewayIdentity("alice", frozenset({"qwen-local"}))
    payload = {
        "model": "qwen-local",
        "messages": [{"role": "user", "content": "hello"}],
        "options": {"temperature": 0.2, "top_p": 0.9, "num_ctx": 8192},
        "keep_alive": "5m",
        "stream": True,
    }

    async def collect() -> list[dict]:
        return [
            json.loads(chunk)
            async for chunk in protocol.stream_ollama_chat(payload, identity, None)
        ]

    chunks = asyncio.run(collect())

    assert chunks[0]["message"]["content"] == "grounded "
    assert chunks[-1]["done"] is True
    assert len(processor.requests) == 1
    assert processor.requests[0].metadata["requested_context_tokens"] == 8192
    assert processor.requests[0].metadata["requested_keep_alive"] == "5m"


@pytest.mark.parametrize(
    "field,value",
    [
        ("tools", [{"type": "function"}]),
        ("messages", [{"role": "user", "content": "x", "images": ["abc"]}]),
    ],
)
def test_ollama_unsupported_semantics_fail_instead_of_being_dropped(field, value) -> None:
    """Tool and image shapes must receive an explicit compatibility error."""
    payload = {
        "model": "qwen-local",
        "messages": [{"role": "user", "content": "hello"}],
        field: value,
    }
    with pytest.raises(GatewayProtocolError, match="not supported"):
        asyncio.run(
            _protocol().ollama_chat(
                payload,
                GatewayIdentity("alice", None),
                None,
            )
        )


def test_embedding_shapes_are_compatible_and_bounded() -> None:
    """Embedding endpoints should reuse the injected Core provider."""
    protocol = _protocol()
    identity = GatewayIdentity("alice", None)

    openai = protocol.embeddings(
        {"model": "embed-model", "input": ["one", "three"]},
        identity,
        ollama=False,
    )
    ollama = protocol.embeddings(
        {"model": "embed-model", "input": "one"}, identity, ollama=True
    )

    assert openai["data"][1]["embedding"] == [5.0]
    assert ollama["embeddings"] == [[3.0]]


def test_managed_http_service_enforces_bearer_and_serves_both_catalogues() -> None:
    """The actual listener should authenticate before exposing protocol routes."""

    class _Config:
        values = {
            ("gateway", "listen_host"): "127.0.0.1",
            ("gateway", "authentication_mode"): "bearer",
            ("gateway", "principal"): "alice",
            ("gateway", "allowed_models"): "qwen-local",
        }

        def config_value(self, section, key, default=None):
            return self.values.get((section, key), default)

        def int_config_value(self, section, key, default=None):
            return self.values.get((section, key), default)

    class _Vault:
        def get(self, key):
            assert key == "api_key"
            return "gateway-secret"

    try:
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
    except PermissionError:
        pytest.skip("The test sandbox does not permit loopback sockets.")
    config = _Config()
    config.values[("gateway", "listen_port")] = port
    context = SimpleNamespace(
        request_processor=_RecordingProcessor(),
        model_catalog_provider=lambda: [{"id": "qwen-local", "owned_by": "orac"}],
        embedding_provider=None,
        plugin_config=lambda: config,
        secret_vault=_Vault(),
        stop_event=threading.Event(),
    )
    service = OracGatewayService()
    thread = threading.Thread(target=service.run, args=(context,))
    thread.start()
    deadline = time.monotonic() + 2
    while not service.state.listening and time.monotonic() < deadline:
        time.sleep(0.01)
    try:
        with pytest.raises(HTTPError) as unauthorised:
            urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=2)
        assert unauthorised.value.code == 401

        headers = {"Authorization": "Bearer gateway-secret"}
        with urlopen(
            Request(f"http://127.0.0.1:{port}/v1/models", headers=headers), timeout=2
        ) as response:
            assert json.load(response)["data"][0]["id"] == "qwen-local"
        with urlopen(
            Request(f"http://127.0.0.1:{port}/api/tags", headers=headers), timeout=2
        ) as response:
            assert json.load(response)["models"][0]["name"] == "qwen-local"
    finally:
        service.stop(context)
        thread.join(timeout=2)
    assert not thread.is_alive()
