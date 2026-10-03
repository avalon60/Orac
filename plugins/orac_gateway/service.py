"""Managed HTTP service for the Orac Gateway plugin."""
# Author: Clive Bostock
# Date: 28-Sep-2026
# Description: Serves OpenAI-compatible and Ollama-native inference endpoints.

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit

from orac_core.communications import ConversationContext

from .auth import GatewayAuthenticationError
from .auth import GatewayAuthenticator
from .models import GatewayConfiguration
from .protocol import GatewayProtocol
from .protocol import GatewayProtocolError


@dataclass(slots=True)
class GatewayServiceState:
    """Redacted operational status for lifecycle health checks."""

    started: bool = False
    listening: bool = False
    stopped: bool = False
    request_count: int = 0
    error_count: int = 0
    active_requests: int = 0
    last_error_code: str | None = None


class _GatewayHttpServer(ThreadingHTTPServer):
    """Thread-per-request server carrying one gateway service reference."""

    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], service: "OracGatewayService") -> None:
        self.gateway_service = service
        super().__init__(address, _GatewayRequestHandler)


class _GatewayRequestHandler(BaseHTTPRequestHandler):
    """Route a bounded HTTP request to the managed gateway service."""

    server: _GatewayHttpServer
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        """Handle model discovery and health requests."""
        self.server.gateway_service.handle_http(self)

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        """Handle chat and embedding requests."""
        self.server.gateway_service.handle_http(self)

    def log_message(self, format: str, *args: object) -> None:
        """Send access summaries through the Orac logger without body content."""
        self.server.gateway_service.log_debug(format % args)


class OracGatewayService:
    """Long-running service plugin implementing the Orac inference gateway."""

    def __init__(
        self,
        logger: Any | None = None,
        config_mgr: Any | None = None,
        manifest: Any | None = None,
        *,
        server_factory: Callable[[tuple[str, int], "OracGatewayService"], Any] | None = None,
    ) -> None:
        """Initialise the service with host dependencies supplied at run time."""
        self._logger = logger
        self._config_mgr = config_mgr
        self._manifest = manifest
        self._server_factory = server_factory or _GatewayHttpServer
        self._server: Any | None = None
        self._server_thread: threading.Thread | None = None
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._protocol: GatewayProtocol | None = None
        self._authenticator: GatewayAuthenticator | None = None
        self._configuration: GatewayConfiguration | None = None
        self._state = GatewayServiceState()
        self._state_lock = threading.Lock()

    @property
    def state(self) -> GatewayServiceState:
        """Return redacted service state for tests and diagnostics."""
        return self._state

    def run(self, context: Any) -> None:
        """Bind the listener and serve until the plugin manager requests stop."""
        if context.request_processor is None:
            raise RuntimeError("Orac Gateway requires the host request processor.")
        if context.model_catalog_provider is None:
            raise RuntimeError("Orac Gateway requires the host model catalogue.")
        configuration = GatewayConfiguration.from_manager(context.plugin_config())
        token = None
        if configuration.authentication_mode == "bearer":
            token = context.secret_vault.get("api_key")
        self._configuration = configuration
        self._authenticator = GatewayAuthenticator(
            mode=configuration.authentication_mode,
            principal=configuration.principal,
            allowed_models=configuration.allowed_models,
            bearer_token=token,
        )
        self._protocol = GatewayProtocol(
            processor=context.request_processor,
            model_catalog_provider=context.model_catalog_provider,
            embedding_provider=context.embedding_provider,
        )
        self._server = self._server_factory(
            (configuration.listen_host, configuration.listen_port), self
        )
        self._state = GatewayServiceState(started=True, listening=True)
        self.log_info(
            "Orac Gateway listening: "
            f"host={configuration.listen_host} port={configuration.listen_port} "
            f"auth={configuration.authentication_mode}"
        )
        self._event_loop = asyncio.new_event_loop()
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.2},
            name="orac-gateway-http",
            daemon=False,
        )
        self._server_thread.start()
        try:
            self._event_loop.run_forever()
        finally:
            self._state.listening = False
            self._state.stopped = True
            self._server.shutdown()
            self._server_thread.join(timeout=5)
            self._server.server_close()
            self._event_loop.close()
            self._event_loop = None

    def stop(self, _context: Any) -> None:
        """Stop accepting requests and unblock the managed service thread."""
        if self._server is not None:
            self._server.shutdown()
        if self._event_loop is not None:
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)

    def health(self, _context: Any) -> bool:
        """Return whether the managed listener is currently available."""
        return self._state.started and self._state.listening and not self._state.stopped

    def handle_command(
        self,
        _context: Any,
        command: str,
        _payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return redacted status through the host-managed command path."""
        if command != "status":
            raise ValueError(f"Unsupported Orac Gateway command '{command}'.")
        return {
            "status": "running" if self.health(_context) else "stopped",
            "listening": self._state.listening,
            "requests": self._state.request_count,
            "errors": self._state.error_count,
            "active_requests": self._state.active_requests,
            "last_error_code": self._state.last_error_code,
        }

    def handle_http(self, handler: _GatewayRequestHandler) -> None:
        """Authenticate and execute one bounded HTTP request."""
        path = urlsplit(handler.path).path
        if path == "/health" and handler.command == "GET":
            self._send_json(handler, 200 if self.health(None) else 503, {"status": "ok"})
            return
        with self._state_lock:
            self._state.request_count += 1
            self._state.active_requests += 1
        try:
            assert self._authenticator is not None
            identity = self._authenticator.authenticate(
                client_host=str(handler.client_address[0]),
                headers=handler.headers,
            )
            if handler.command == "GET":
                self._handle_get(handler, path, identity)
            elif handler.command == "POST":
                self._handle_post(handler, path, identity)
            else:
                raise GatewayProtocolError(405, "method_not_allowed", "Method not allowed.")
        except GatewayAuthenticationError as exc:
            self._record_error("unauthorised")
            self._send_error(handler, 401, "unauthorised", str(exc))
        except GatewayProtocolError as exc:
            self._record_error(exc.code)
            self._send_error(handler, exc.status, exc.code, str(exc))
        except (BrokenPipeError, ConnectionResetError):
            self._record_error("client_disconnected")
        except Exception:
            self._record_error("internal_error")
            self._send_error(handler, 500, "internal_error", "Gateway request failed.")
        finally:
            with self._state_lock:
                self._state.active_requests = max(0, self._state.active_requests - 1)

    def _handle_get(self, handler: _GatewayRequestHandler, path: str, identity: Any) -> None:
        assert self._protocol is not None
        if path == "/v1/models":
            self._send_json(handler, 200, self._protocol.openai_models(identity))
            return
        if path == "/api/tags":
            self._send_json(handler, 200, self._protocol.ollama_tags(identity))
            return
        raise GatewayProtocolError(404, "not_found", "Endpoint not found.")

    def _handle_post(self, handler: _GatewayRequestHandler, path: str, identity: Any) -> None:
        assert self._protocol is not None
        payload = self._read_json(handler)
        context = self._conversation_context(handler, identity.principal)
        if path == "/v1/chat/completions":
            if bool(payload.get("stream")):
                self._protocol.validate_openai_chat(payload, identity, context)
                self._send_stream(
                    handler,
                    "text/event-stream",
                    self._protocol.stream_openai_chat(payload, identity, context),
                )
            else:
                result = self._run_async(
                    self._protocol.openai_chat(payload, identity, context)
                )
                self._send_json(handler, _result_status(result), result)
            return
        if path == "/api/chat":
            if bool(payload.get("stream", True)):
                self._protocol.validate_ollama_chat(payload, identity, context)
                self._send_stream(
                    handler,
                    "application/x-ndjson",
                    self._protocol.stream_ollama_chat(payload, identity, context),
                )
            else:
                result = self._run_async(
                    self._protocol.ollama_chat(payload, identity, context)
                )
                self._send_json(handler, _result_status(result), result)
            return
        if path in {"/v1/embeddings", "/api/embed"}:
            result = self._protocol.embeddings(payload, identity, ollama=path == "/api/embed")
            self._send_json(handler, 200, result)
            return
        raise GatewayProtocolError(404, "not_found", "Endpoint not found.")

    def _read_json(self, handler: _GatewayRequestHandler) -> dict[str, Any]:
        assert self._configuration is not None
        try:
            length = int(handler.headers.get("Content-Length") or "0")
        except ValueError as exc:
            raise GatewayProtocolError(400, "invalid_request_error", "Invalid Content-Length.") from exc
        if length <= 0:
            raise GatewayProtocolError(400, "invalid_request_error", "A JSON request body is required.")
        if length > self._configuration.max_request_bytes:
            raise GatewayProtocolError(413, "request_too_large", "Request body is too large.")
        try:
            value = json.loads(handler.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise GatewayProtocolError(400, "invalid_request_error", "Request body is not valid JSON.") from exc
        if not isinstance(value, dict):
            raise GatewayProtocolError(400, "invalid_request_error", "Request body must be an object.")
        return value

    @staticmethod
    def _conversation_context(handler: _GatewayRequestHandler, principal: str) -> ConversationContext:
        supplied = str(handler.headers.get("X-Orac-Session-ID") or "").strip()
        session_id = f"gateway:{principal}:{supplied[:128]}" if supplied else None
        return ConversationContext(session_id=session_id)

    def _send_stream(
        self,
        handler: _GatewayRequestHandler,
        content_type: str,
        stream: Any,
    ) -> None:
        handler.send_response(200)
        handler.send_header("Content-Type", content_type)
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "close")
        handler.end_headers()

        async def consume() -> None:
            async for chunk in stream:
                handler.wfile.write(chunk)
                handler.wfile.flush()

        self._run_async(consume())

    def _run_async(self, coroutine: Any) -> Any:
        """Execute Core work on the service-owned event loop."""
        loop = self._event_loop
        if loop is None or not loop.is_running():
            raise RuntimeError("Orac Gateway event loop is not running.")
        return asyncio.run_coroutine_threadsafe(coroutine, loop).result()

    @staticmethod
    def _send_json(handler: _GatewayRequestHandler, status: int, value: Mapping[str, Any]) -> None:
        body = json.dumps(dict(value), ensure_ascii=False).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.send_header("Connection", "close")
        handler.end_headers()
        handler.wfile.write(body)

    def _send_error(
        self,
        handler: _GatewayRequestHandler,
        status: int,
        code: str,
        message: str,
    ) -> None:
        self._send_json(
            handler,
            status,
            {"error": {"message": message, "type": "gateway_error", "code": code}},
        )

    def _record_error(self, code: str) -> None:
        with self._state_lock:
            self._state.error_count += 1
            self._state.last_error_code = code

    def log_info(self, message: str) -> None:
        """Write an informational message when a host logger is available."""
        if self._logger is not None:
            self._logger.log_info(message)

    def log_debug(self, message: str) -> None:
        """Write a debug message when a host logger is available."""
        if self._logger is not None:
            self._logger.log_debug(message)


def _result_status(result: Mapping[str, Any]) -> int:
    """Return an HTTP status for a canonical safe error projection."""
    error = result.get("error")
    if not isinstance(error, Mapping):
        return 200
    code = str(error.get("code") or "")
    if code in {"unauthorised", "model_not_authorised"}:
        return 403
    return 502 if error.get("type") == "server_error" else 400
