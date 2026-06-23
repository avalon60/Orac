"""Home Assistant API client for the managed Orac plugin service."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Provides small testable REST and WebSocket HA API access.

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import os
import re
import socket
import ssl
import struct
from typing import Any

import requests

__author__ = "Clive Bostock"
__date__ = "04-Jun-2026"
__description__ = "Provides small testable REST and WebSocket HA API access."


class HomeAssistantClientError(RuntimeError):
    """Raised when the Home Assistant REST API cannot satisfy a request."""


@dataclass(frozen=True)
class HomeAssistantClientConfig:
    """Connection settings for the Home Assistant REST API."""

    protocol: str
    host: str
    port: int
    token: str
    verify_ssl: bool = True
    timeout_seconds: float = 10.0
    websocket_path: str = "/api/websocket"


class HomeAssistantClient:
    """Small Home Assistant API client used by the managed service."""

    def __init__(
        self,
        config: HomeAssistantClientConfig,
        *,
        session: Any | None = None,
        websocket_session: Any | None = None,
    ) -> None:
        """Initialise the client.

        Args:
            config: Home Assistant connection settings.
            session: Optional requests-compatible session for tests.
            websocket_session: Optional WebSocket-command session for tests.
        """
        self._config = config
        self._session = session or requests.Session()
        self._websocket_session = websocket_session
        self.base_url = _base_url(config.protocol, config.host, config.port)
        self._session.headers.update(
            {
                "Authorization": f"Bearer {config.token}",
                "Content-Type": "application/json",
            }
        )

    def check_api(self) -> bool:
        """Return whether Home Assistant reports API availability."""
        payload = self._get_json("/api/")
        if isinstance(payload, dict):
            return True
        raise HomeAssistantClientError("Home Assistant API check returned unexpected payload.")

    def fetch_areas(self) -> list[dict[str, Any]]:
        """Fetch Home Assistant area registry entries."""
        return self._websocket_list("config/area_registry/list")

    def fetch_devices(self) -> list[dict[str, Any]]:
        """Fetch Home Assistant device registry entries."""
        return self._websocket_list("config/device_registry/list")

    def fetch_entities(self) -> list[dict[str, Any]]:
        """Fetch Home Assistant entity registry entries."""
        return self._websocket_list("config/entity_registry/list")

    def fetch_states(self) -> list[dict[str, Any]]:
        """Fetch current Home Assistant entity states."""
        return self._get_list("/api/states")

    def fetch_state(self, entity_id: str) -> dict[str, Any]:
        """Fetch current state for one resolved Home Assistant entity."""
        safe_entity_id = str(entity_id or "").strip().lower()
        if not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", safe_entity_id):
            raise HomeAssistantClientError("Invalid Home Assistant entity ID.")
        payload = self._get_json(f"/api/states/{safe_entity_id}")
        if not isinstance(payload, dict):
            raise HomeAssistantClientError(
                f"Home Assistant state for '{safe_entity_id}' returned unexpected payload."
            )
        returned_entity_id = str(payload.get("entity_id") or "").strip().lower()
        if returned_entity_id != safe_entity_id:
            raise HomeAssistantClientError(
                f"Home Assistant returned the wrong entity for '{safe_entity_id}'."
            )
        return payload

    def call_service(
        self,
        domain: str,
        service: str,
        entity_ids: tuple[str, ...],
        data: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Call one prevalidated Home Assistant service.

        Args:
            domain: Allowlisted Home Assistant domain.
            service: Allowlisted Home Assistant service.
            entity_ids: Resolved entity IDs to address.
            data: Optional service payload merged with ``entity_id``.

        Returns:
            Home Assistant state objects confirming the service call.

        Raises:
            HomeAssistantClientError: If the request fails or payload is invalid.
        """
        path = f"/api/services/{domain}/{service}"
        url = f"{self.base_url}{path}"
        payload = {"entity_id": list(entity_ids)}
        if data:
            payload.update(data)
        try:
            response = self._session.post(
                url,
                json=payload,
                timeout=self._config.timeout_seconds,
                verify=self._config.verify_ssl,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.Timeout as exc:
            raise HomeAssistantClientError(
                f"Home Assistant service call timed out for '{domain}.{service}'."
            ) from exc
        except requests.RequestException as exc:
            raise HomeAssistantClientError(
                f"Home Assistant service call failed for '{domain}.{service}'."
            ) from exc
        except ValueError as exc:
            raise HomeAssistantClientError(
                f"Home Assistant service '{domain}.{service}' returned invalid JSON."
            ) from exc
        if not isinstance(payload, list) or any(
            not isinstance(item, dict) for item in payload
        ):
            raise HomeAssistantClientError(
                f"Home Assistant service '{domain}.{service}' returned unexpected payload."
            )
        return payload

    def close(self) -> None:
        """Close the underlying HTTP session when supported."""
        close = getattr(self._session, "close", None)
        if callable(close):
            close()
        if self._websocket_session is not None:
            websocket_close = getattr(self._websocket_session, "close", None)
            if callable(websocket_close):
                websocket_close()

    def _get_list(self, path: str) -> list[dict[str, Any]]:
        """Fetch a JSON list and reject unexpected payload shapes."""
        payload = self._get_json(path)
        if not isinstance(payload, list):
            raise HomeAssistantClientError(
                f"Home Assistant endpoint '{path}' returned unexpected payload."
            )
        for item in payload:
            if not isinstance(item, dict):
                raise HomeAssistantClientError(
                    f"Home Assistant endpoint '{path}' returned a non-object item."
                )
        return payload

    def _get_json(self, path: str) -> Any:
        """Fetch one Home Assistant endpoint as JSON."""
        url = f"{self.base_url}{path}"
        try:
            response = self._session.get(
                url,
                timeout=self._config.timeout_seconds,
                verify=self._config.verify_ssl,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise HomeAssistantClientError(
                f"Home Assistant request failed for endpoint '{path}'."
            ) from exc
        except ValueError as exc:
            raise HomeAssistantClientError(
                f"Home Assistant endpoint '{path}' returned invalid JSON."
            ) from exc

    def _websocket_list(self, command: str) -> list[dict[str, Any]]:
        """Run one Home Assistant WebSocket command and require a list result."""
        payload = self._websocket_command(command)
        if not isinstance(payload, list):
            raise HomeAssistantClientError(
                f"Home Assistant WebSocket command '{command}' returned unexpected payload."
            )
        for item in payload:
            if not isinstance(item, dict):
                raise HomeAssistantClientError(
                    f"Home Assistant WebSocket command '{command}' returned a non-object item."
                )
        return payload

    def _websocket_command(self, command: str) -> Any:
        """Run one command through Home Assistant's WebSocket API."""
        session = self._websocket_session
        if session is None:
            session = _HomeAssistantWebSocketSession(self._config)
            self._websocket_session = session
        try:
            return session.command(command)
        except HomeAssistantClientError:
            raise
        except OSError as exc:
            raise HomeAssistantClientError(
                f"Home Assistant WebSocket command failed for '{command}'."
            ) from exc


def _base_url(protocol: str, host: str, port: int) -> str:
    """Return a normalised Home Assistant base URL."""
    safe_protocol = str(protocol or "http").strip().lower()
    safe_host = str(host or "").strip().rstrip("/")
    if not safe_host:
        raise HomeAssistantClientError("Home Assistant host is required.")
    if safe_protocol not in {"http", "https"}:
        raise HomeAssistantClientError("Home Assistant protocol must be http or https.")
    return f"{safe_protocol}://{safe_host}:{int(port)}"


class _HomeAssistantWebSocketSession:
    """Minimal Home Assistant WebSocket command session.

    This intentionally implements only the small subset needed for registry
    list commands, avoiding a runtime dependency for the plugin service.
    """

    _GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    def __init__(self, config: HomeAssistantClientConfig) -> None:
        """Create a lazy WebSocket session for Home Assistant commands."""
        self._config = config
        self._socket: socket.socket | ssl.SSLSocket | None = None
        self._next_id = 1
        self._authenticated = False

    def command(self, command_type: str) -> Any:
        """Send one Home Assistant WebSocket command and return its result."""
        self._ensure_authenticated()
        command_id = self._next_id
        self._next_id += 1
        self._send_json({"id": command_id, "type": command_type})
        while True:
            message = self._receive_json()
            if message.get("id") != command_id:
                continue
            if message.get("type") != "result":
                raise HomeAssistantClientError(
                    f"Home Assistant WebSocket command '{command_type}' returned "
                    f"unexpected message type '{message.get('type')}'."
                )
            if not message.get("success"):
                error = message.get("error") or {}
                raise HomeAssistantClientError(
                    f"Home Assistant WebSocket command '{command_type}' failed: "
                    f"{error.get('message') or error.get('code') or 'unknown error'}."
                )
            return message.get("result")

    def close(self) -> None:
        """Close the WebSocket session."""
        sock = self._socket
        self._socket = None
        self._authenticated = False
        if sock is None:
            return
        try:
            self._send_frame(sock, 0x8, b"")
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    def _ensure_authenticated(self) -> None:
        """Connect and authenticate to Home Assistant when needed."""
        if self._authenticated and self._socket is not None:
            return
        sock = self._connect()
        self._socket = sock
        auth_required = self._receive_json()
        if auth_required.get("type") != "auth_required":
            raise HomeAssistantClientError(
                "Home Assistant WebSocket did not request authentication."
            )
        self._send_json({"type": "auth", "access_token": self._config.token})
        auth_response = self._receive_json()
        if auth_response.get("type") != "auth_ok":
            raise HomeAssistantClientError("Home Assistant WebSocket authentication failed.")
        self._authenticated = True

    def _connect(self) -> socket.socket | ssl.SSLSocket:
        """Open and upgrade a socket to the Home Assistant WebSocket API."""
        raw_socket = socket.create_connection(
            (self._config.host, self._config.port),
            timeout=self._config.timeout_seconds,
        )
        if self._config.protocol == "https":
            context = ssl.create_default_context()
            if not self._config.verify_ssl:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            sock: socket.socket | ssl.SSLSocket = context.wrap_socket(
                raw_socket,
                server_hostname=self._config.host,
            )
        else:
            sock = raw_socket
        sock.settimeout(self._config.timeout_seconds)

        path = self._config.websocket_path or "/api/websocket"
        if not path.startswith("/"):
            path = "/" + path
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        host_header = f"{self._config.host}:{self._config.port}"
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host_header}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = _read_http_headers(sock)
        if not response.startswith("HTTP/1.1 101"):
            sock.close()
            raise HomeAssistantClientError("Home Assistant WebSocket upgrade failed.")
        expected_accept = base64.b64encode(
            hashlib.sha1((key + self._GUID).encode("ascii")).digest()
        ).decode("ascii")
        if expected_accept not in response:
            sock.close()
            raise HomeAssistantClientError("Home Assistant WebSocket upgrade was invalid.")
        return sock

    def _send_json(self, payload: dict[str, Any]) -> None:
        """Send one JSON message."""
        if self._socket is None:
            raise HomeAssistantClientError("Home Assistant WebSocket is not connected.")
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self._send_frame(self._socket, 0x1, data)

    def _receive_json(self) -> dict[str, Any]:
        """Read the next text JSON message."""
        if self._socket is None:
            raise HomeAssistantClientError("Home Assistant WebSocket is not connected.")
        while True:
            opcode, payload = self._read_frame(self._socket)
            if opcode == 0x1:
                try:
                    message = json.loads(payload.decode("utf-8"))
                except ValueError as exc:
                    raise HomeAssistantClientError(
                        "Home Assistant WebSocket returned invalid JSON."
                    ) from exc
                if not isinstance(message, dict):
                    raise HomeAssistantClientError(
                        "Home Assistant WebSocket returned unexpected payload."
                    )
                return message
            if opcode == 0x8:
                raise HomeAssistantClientError("Home Assistant WebSocket closed.")
            if opcode == 0x9:
                self._send_frame(self._socket, 0xA, payload)

    @staticmethod
    def _send_frame(sock: socket.socket | ssl.SSLSocket, opcode: int, payload: bytes) -> None:
        """Send one masked client WebSocket frame."""
        length = len(payload)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(0x80 | length)
        elif length <= 0xFFFF:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        masked_payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        sock.sendall(bytes(header) + mask + masked_payload)

    @staticmethod
    def _read_frame(sock: socket.socket | ssl.SSLSocket) -> tuple[int, bytes]:
        """Read one WebSocket frame from the server."""
        first_two = _recv_exact(sock, 2)
        first, second = first_two[0], first_two[1]
        opcode = first & 0x0F
        length = second & 0x7F
        masked = bool(second & 0x80)
        if length == 126:
            length = struct.unpack("!H", _recv_exact(sock, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", _recv_exact(sock, 8))[0]
        mask = _recv_exact(sock, 4) if masked else b""
        payload = _recv_exact(sock, length)
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return opcode, payload


def _read_http_headers(sock: socket.socket | ssl.SSLSocket) -> str:
    """Read an HTTP response header block from a socket."""
    data = bytearray()
    while b"\r\n\r\n" not in data:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > 65536:
            raise HomeAssistantClientError("Home Assistant WebSocket response was too large.")
    return data.decode("iso-8859-1", errors="replace")


def _recv_exact(sock: socket.socket | ssl.SSLSocket, byte_count: int) -> bytes:
    """Receive exactly ``byte_count`` bytes or raise."""
    data = bytearray()
    while len(data) < byte_count:
        chunk = sock.recv(byte_count - len(data))
        if not chunk:
            raise HomeAssistantClientError("Home Assistant WebSocket connection closed.")
        data.extend(chunk)
    return bytes(data)
