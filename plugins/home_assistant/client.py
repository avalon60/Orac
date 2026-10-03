"""Home Assistant API client for the managed Orac plugin service."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Provides small testable REST and WebSocket HA API access.

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import ssl
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
        websocket_app_factory: Any | None = None,
    ) -> None:
        """Initialise the client.

        Args:
            config: Home Assistant connection settings.
            session: Optional requests-compatible session for tests.
            websocket_session: Optional WebSocket-command session for tests.
            websocket_app_factory: Optional websocket-client app factory for tests.
        """
        self._config = config
        self._session = session or requests.Session()
        self._websocket_session = websocket_session
        self._websocket_app_factory = websocket_app_factory
        self._event_app: Any | None = None
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

    def fetch_services(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Fetch Home Assistant action descriptions keyed by domain and name."""
        payload = self._websocket_command("get_services")
        if not isinstance(payload, dict):
            raise HomeAssistantClientError(
                "Home Assistant service discovery returned unexpected payload."
            )
        return payload

    def fetch_services_for_entity(self, entity_id: str) -> tuple[str, ...]:
        """Fetch action identifiers Home Assistant considers applicable."""
        safe_entity_id = _entity_id(entity_id)
        payload = self._websocket_command(
            "get_services_for_target",
            {"target": {"entity_id": [safe_entity_id]}, "expand_group": False},
        )
        if not isinstance(payload, list) or any(not isinstance(item, str) for item in payload):
            raise HomeAssistantClientError(
                "Home Assistant target service discovery returned unexpected payload."
            )
        return tuple(sorted(set(payload)))

    def fetch_state(self, entity_id: str) -> dict[str, Any]:
        """Fetch current state for one resolved Home Assistant entity."""
        safe_entity_id = _entity_id(entity_id)
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

    def listen_events(
        self,
        callback: Any,
        *,
        reconnect_seconds: float = 10.0,
        ping_interval_seconds: float = 30.0,
        ping_timeout_seconds: float = 10.0,
    ) -> None:
        """Listen for HA events with library-owned framing and reconnects.

        Home Assistant authentication, subscription commands, and event
        envelopes remain protocol semantics owned by this client.
        """
        try:
            import websocket
        except ImportError as exc:
            raise HomeAssistantClientError(
                "The websocket-client dependency is required for Home Assistant."
            ) from exc

        factory = self._websocket_app_factory or websocket.WebSocketApp
        url = _websocket_url(self._config)
        subscription_id = 1
        authenticated = False

        def on_message(app: Any, raw_message: str) -> None:
            nonlocal authenticated
            try:
                message = json.loads(raw_message)
            except (TypeError, ValueError):
                return
            if not isinstance(message, dict):
                return
            message_type = message.get("type")
            if message_type == "auth_required":
                app.send(
                    json.dumps(
                        {"type": "auth", "access_token": self._config.token},
                        separators=(",", ":"),
                    )
                )
            elif message_type == "auth_ok":
                authenticated = True
                app.send(
                    json.dumps(
                        {"id": subscription_id, "type": "subscribe_events"},
                        separators=(",", ":"),
                    )
                )
            elif message_type == "auth_invalid":
                authenticated = False
                app.close()
            elif authenticated and message_type == "event" and message.get("id") == subscription_id:
                event = message.get("event")
                if isinstance(event, dict):
                    callback(event)

        def on_close(_app: Any, _status: Any, _message: Any) -> None:
            nonlocal authenticated
            authenticated = False

        app = factory(url, on_message=on_message, on_close=on_close)
        self._event_app = app
        ssl_options = (
            {"cert_reqs": ssl.CERT_NONE, "check_hostname": False}
            if self._config.protocol == "https" and not self._config.verify_ssl
            else {}
        )
        try:
            app.run_forever(
                sslopt=ssl_options,
                ping_interval=ping_interval_seconds,
                ping_timeout=ping_timeout_seconds,
                reconnect=max(0, int(reconnect_seconds)),
            )
        finally:
            if self._event_app is app:
                self._event_app = None

    def close(self) -> None:
        """Close the underlying HTTP session when supported."""
        close = getattr(self._session, "close", None)
        if callable(close):
            close()
        if self._websocket_session is not None:
            websocket_close = getattr(self._websocket_session, "close", None)
            if callable(websocket_close):
                websocket_close()
        event_app = self._event_app
        self._event_app = None
        if event_app is not None:
            try:
                event_app.close()
            except Exception:
                pass

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

    def _websocket_command(
        self,
        command: str,
        fields: dict[str, Any] | None = None,
    ) -> Any:
        """Run one command through Home Assistant's WebSocket API."""
        session = self._websocket_session
        if session is None:
            session = _HomeAssistantWebSocketSession(self._config)
            self._websocket_session = session
        try:
            if fields:
                return session.command(command, fields)
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


def _websocket_url(config: HomeAssistantClientConfig) -> str:
    """Return the configured Home Assistant WebSocket URL."""
    scheme = "wss" if config.protocol == "https" else "ws"
    path = config.websocket_path or "/api/websocket"
    if not path.startswith("/"):
        path = "/" + path
    return f"{scheme}://{config.host}:{config.port}{path}"


def _entity_id(value: str) -> str:
    """Return a validated canonical Home Assistant entity identifier."""
    entity_id = str(value or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", entity_id):
        raise HomeAssistantClientError("Invalid Home Assistant entity ID.")
    return entity_id


class _HomeAssistantWebSocketSession:
    """Home Assistant protocol session over ``websocket-client`` transport."""

    def __init__(self, config: HomeAssistantClientConfig) -> None:
        """Create a lazy WebSocket session for Home Assistant commands."""
        self._config = config
        self._socket: Any | None = None
        self._next_id = 1
        self._authenticated = False

    def command(
        self,
        command_type: str,
        fields: dict[str, Any] | None = None,
    ) -> Any:
        """Send one Home Assistant WebSocket command and return its result."""
        self._ensure_authenticated()
        command_id = self._next_id
        self._next_id += 1
        self._send_json({"id": command_id, "type": command_type, **(fields or {})})
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
            sock.close()
        except Exception:
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

    def _connect(self) -> Any:
        """Create a maintained-library WebSocket transport."""
        try:
            import websocket
        except ImportError as exc:
            raise HomeAssistantClientError(
                "The websocket-client dependency is required for Home Assistant."
            ) from exc

        scheme = "wss" if self._config.protocol == "https" else "ws"
        ssl_options = (
            {"cert_reqs": 0, "check_hostname": False}
            if scheme == "wss" and not self._config.verify_ssl
            else {}
        )
        try:
            return websocket.create_connection(
                _websocket_url(self._config),
                timeout=self._config.timeout_seconds,
                sslopt=ssl_options,
            )
        except Exception as exc:
            raise HomeAssistantClientError(
                "Home Assistant WebSocket connection failed."
            ) from exc

    def _send_json(self, payload: dict[str, Any]) -> None:
        """Send one JSON message."""
        if self._socket is None:
            raise HomeAssistantClientError("Home Assistant WebSocket is not connected.")
        try:
            self._socket.send(json.dumps(payload, separators=(",", ":")))
        except Exception as exc:
            raise HomeAssistantClientError(
                "Home Assistant WebSocket send failed."
            ) from exc

    def _receive_json(self) -> dict[str, Any]:
        """Read the next text JSON message."""
        if self._socket is None:
            raise HomeAssistantClientError("Home Assistant WebSocket is not connected.")
        try:
            raw_message = self._socket.recv()
        except Exception as exc:
            raise HomeAssistantClientError(
                "Home Assistant WebSocket receive failed or timed out."
            ) from exc
        try:
            message = json.loads(raw_message)
        except (TypeError, ValueError) as exc:
            raise HomeAssistantClientError(
                "Home Assistant WebSocket returned invalid JSON."
            ) from exc
        if not isinstance(message, dict):
            raise HomeAssistantClientError(
                "Home Assistant WebSocket returned unexpected payload."
            )
        return message
