"""Tests for the Home Assistant API client."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Verifies Home Assistant REST and WebSocket usage without network calls.

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
for path in (SRC_ROOT, PLUGINS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from home_assistant.client import HomeAssistantClient
from home_assistant.client import HomeAssistantClientConfig
from home_assistant.client import HomeAssistantClientError
from home_assistant.client import _HomeAssistantWebSocketSession


class _FakeResponse:
    def __init__(self, payload, *, fail: bool = False) -> None:
        self.payload = payload
        self.fail = fail

    def raise_for_status(self) -> None:
        if self.fail:
            raise requests.HTTPError("http failed")

    def json(self):
        return self.payload


class _FakeSession:
    def __init__(self, responses: dict[str, _FakeResponse]) -> None:
        self.headers: dict[str, str] = {}
        self.responses = responses
        self.calls: list[dict] = []
        self.closed = False

    def get(self, url: str, *, timeout: float, verify: bool):
        self.calls.append({"url": url, "timeout": timeout, "verify": verify})
        return self.responses[url]

    def post(self, url: str, *, json: dict, timeout: float, verify: bool):
        self.calls.append(
            {
                "url": url,
                "json": json,
                "timeout": timeout,
                "verify": verify,
            }
        )
        response = self.responses[url]
        if isinstance(response, BaseException):
            raise response
        return response

    def close(self) -> None:
        self.closed = True


class _FakeWebSocketSession:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.commands: list[str] = []
        self.command_fields: list[dict | None] = []
        self.closed = False

    def command(self, command: str, fields: dict | None = None):
        self.commands.append(command)
        self.command_fields.append(fields)
        response = self.responses[command]
        if isinstance(response, BaseException):
            raise response
        return response

    def close(self) -> None:
        self.closed = True


class _FakeLibrarySocket:
    """Minimal websocket-client compatible socket for transport tests."""

    def __init__(self, messages: list[dict | BaseException]) -> None:
        self.messages = [
            message if isinstance(message, BaseException) else json.dumps(message)
            for message in messages
        ]
        self.sent: list[dict] = []
        self.closed = False

    def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    def recv(self) -> str:
        message = self.messages.pop(0)
        if isinstance(message, BaseException):
            raise message
        return message

    def close(self) -> None:
        self.closed = True


class _FakeWebSocketApp:
    """websocket-client app double that emits one authenticated event."""

    def __init__(self, url: str, *, on_message, on_close) -> None:
        self.url = url
        self.on_message = on_message
        self.on_close = on_close
        self.sent: list[dict] = []
        self.run_options: dict = {}
        self.closed = False

    def send(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    def run_forever(self, **kwargs) -> None:
        self.run_options = kwargs
        self.on_message(self, json.dumps({"type": "auth_required"}))
        self.on_message(self, json.dumps({"type": "auth_ok"}))
        self.on_message(
            self,
            json.dumps(
                {
                    "id": 1,
                    "type": "event",
                    "event": {"event_type": "state_changed", "data": {"new_state": {"entity_id": "light.a"}}},
                }
            ),
        )

    def close(self) -> None:
        self.closed = True


def _client(
    session: _FakeSession,
    websocket_session: _FakeWebSocketSession | None = None,
) -> HomeAssistantClient:
    return HomeAssistantClient(
        HomeAssistantClientConfig(
            protocol="http",
            host="ha.local",
            port=8123,
            token="secret-token",
            verify_ssl=False,
        ),
        session=session,
        websocket_session=websocket_session,
    )


class HomeAssistantClientTests(unittest.TestCase):
    """Tests Home Assistant REST client behaviour."""

    def test_builds_base_url_and_authorization_headers(self) -> None:
        session = _FakeSession({})

        client = _client(session)

        self.assertEqual(client.base_url, "http://ha.local:8123")
        self.assertEqual(session.headers["Authorization"], "Bearer secret-token")
        self.assertEqual(session.headers["Content-Type"], "application/json")

    def test_check_api_success_uses_api_endpoint(self) -> None:
        session = _FakeSession(
            {"http://ha.local:8123/api/": _FakeResponse({"message": "API running."})}
        )
        client = _client(session)

        self.assertTrue(client.check_api())

        self.assertEqual(session.calls[0]["url"], "http://ha.local:8123/api/")
        self.assertFalse(session.calls[0]["verify"])

    def test_check_api_failure_raises_clean_error(self) -> None:
        session = _FakeSession(
            {"http://ha.local:8123/api/": _FakeResponse({}, fail=True)}
        )
        client = _client(session)

        with self.assertRaises(HomeAssistantClientError):
            client.check_api()

    def test_fetches_structural_data_through_websocket_commands(self) -> None:
        session = _FakeSession({})
        websocket_session = _FakeWebSocketSession(
            {
                "config/area_registry/list": [{"area_id": "kitchen"}],
                "config/device_registry/list": [{"id": "device-1"}],
                "config/entity_registry/list": [{"entity_id": "light.kitchen"}],
            }
        )
        client = _client(session, websocket_session)

        self.assertEqual(client.fetch_areas(), [{"area_id": "kitchen"}])
        self.assertEqual(client.fetch_devices(), [{"id": "device-1"}])
        self.assertEqual(client.fetch_entities(), [{"entity_id": "light.kitchen"}])
        self.assertEqual(
            websocket_session.commands,
            [
                "config/area_registry/list",
                "config/device_registry/list",
                "config/entity_registry/list",
            ],
        )
        self.assertEqual(session.calls, [])

    def test_fetches_states_endpoint_using_rest(self) -> None:
        session = _FakeSession(
            {
                "http://ha.local:8123/api/states": _FakeResponse(
                    [{"entity_id": "light.kitchen", "state": "on"}]
                ),
            }
        )
        client = _client(session)

        self.assertEqual(
            client.fetch_states(),
            [{"entity_id": "light.kitchen", "state": "on"}],
        )

    def test_discovers_global_and_entity_specific_services(self) -> None:
        services = {"light": {"turn_on": {"fields": {}}}}
        websocket_session = _FakeWebSocketSession(
            {
                "get_services": services,
                "get_services_for_target": ["light.turn_on"],
            }
        )
        client = _client(_FakeSession({}), websocket_session)

        self.assertEqual(client.fetch_services(), services)
        self.assertEqual(
            client.fetch_services_for_entity("light.kitchen"),
            ("light.turn_on",),
        )
        self.assertEqual(
            websocket_session.command_fields[-1],
            {
                "target": {"entity_id": ["light.kitchen"]},
                "expand_group": False,
            },
        )

    def test_library_transport_handles_connection_auth_and_command_correlation(self) -> None:
        socket = _FakeLibrarySocket(
            [
                {"type": "auth_required"},
                {"type": "auth_ok"},
                {"id": 999, "type": "event", "event": {}},
                {"id": 1, "type": "result", "success": True, "result": ["light.turn_on"]},
            ]
        )
        config = HomeAssistantClientConfig(
            protocol="https",
            host="ha.local",
            port=8123,
            token="secret-token",
            verify_ssl=False,
            timeout_seconds=4.5,
        )

        with patch("websocket.create_connection", return_value=socket) as connect:
            session = _HomeAssistantWebSocketSession(config)
            result = session.command("get_services_for_target", {"target": {"entity_id": ["light.a"]}})
            session.close()

        self.assertEqual(result, ["light.turn_on"])
        connect.assert_called_once_with(
            "wss://ha.local:8123/api/websocket",
            timeout=4.5,
            sslopt={"cert_reqs": 0, "check_hostname": False},
        )
        self.assertEqual(socket.sent[0], {"type": "auth", "access_token": "secret-token"})
        self.assertEqual(
            socket.sent[1],
            {
                "id": 1,
                "type": "get_services_for_target",
                "target": {"entity_id": ["light.a"]},
            },
        )
        self.assertTrue(socket.closed)

    def test_library_transport_translates_connection_failure(self) -> None:
        config = HomeAssistantClientConfig(
            protocol="http",
            host="ha.local",
            port=8123,
            token="secret-token",
        )
        with patch("websocket.create_connection", side_effect=OSError("offline")):
            with self.assertRaisesRegex(HomeAssistantClientError, "connection failed"):
                _HomeAssistantWebSocketSession(config).command("get_services")

    def test_library_transport_translates_receive_timeout(self) -> None:
        socket = _FakeLibrarySocket(
            [
                {"type": "auth_required"},
                {"type": "auth_ok"},
                TimeoutError("slow"),
            ]
        )
        config = HomeAssistantClientConfig(
            protocol="http",
            host="ha.local",
            port=8123,
            token="secret-token",
        )

        with patch("websocket.create_connection", return_value=socket):
            with self.assertRaisesRegex(HomeAssistantClientError, "timed out"):
                _HomeAssistantWebSocketSession(config).command("get_services")

    def test_event_listener_uses_library_reconnect_and_ha_subscription(self) -> None:
        holder: dict[str, _FakeWebSocketApp] = {}

        def factory(url: str, **callbacks):
            app = _FakeWebSocketApp(url, **callbacks)
            holder["app"] = app
            return app

        client = HomeAssistantClient(
            HomeAssistantClientConfig(
                protocol="https",
                host="ha.local",
                port=8123,
                token="secret-token",
                verify_ssl=False,
            ),
            session=_FakeSession({}),
            websocket_app_factory=factory,
        )
        events: list[dict] = []

        client.listen_events(events.append, reconnect_seconds=7)

        app = holder["app"]
        self.assertEqual(app.url, "wss://ha.local:8123/api/websocket")
        self.assertEqual(
            app.sent,
            [
                {"type": "auth", "access_token": "secret-token"},
                {"id": 1, "type": "subscribe_events"},
            ],
        )
        self.assertEqual(app.run_options["reconnect"], 7)
        self.assertEqual(len(events), 1)

    def test_fetches_one_resolved_entity_state_using_rest(self) -> None:
        url = "http://ha.local:8123/api/states/sensor.lounge_temperature"
        session = _FakeSession(
            {
                url: _FakeResponse(
                    {
                        "entity_id": "sensor.lounge_temperature",
                        "state": "18.9",
                    }
                )
            }
        )
        client = _client(session)

        result = client.fetch_state("sensor.lounge_temperature")

        self.assertEqual(result["state"], "18.9")
        self.assertEqual(session.calls[0]["url"], url)

    def test_fetch_state_rejects_untrusted_entity_id(self) -> None:
        client = _client(_FakeSession({}))

        with self.assertRaisesRegex(HomeAssistantClientError, "Invalid"):
            client.fetch_state("sensor.lounge/temperature")

    def test_fetch_state_rejects_mismatched_entity_response(self) -> None:
        url = "http://ha.local:8123/api/states/sensor.lounge_temperature"
        client = _client(
            _FakeSession(
                {
                    url: _FakeResponse(
                        {"entity_id": "sensor.other_temperature", "state": "18.9"}
                    )
                }
            )
        )

        with self.assertRaisesRegex(HomeAssistantClientError, "wrong entity"):
            client.fetch_state("sensor.lounge_temperature")

    def test_unexpected_list_payload_raises(self) -> None:
        session = _FakeSession(
            {
                "http://ha.local:8123/api/states": _FakeResponse(
                    {"entity_id": "light.kitchen"}
                )
            }
        )
        client = _client(session)

        with self.assertRaises(HomeAssistantClientError):
            client.fetch_states()

    def test_unexpected_websocket_list_payload_raises(self) -> None:
        client = _client(
            _FakeSession({}),
            _FakeWebSocketSession({"config/area_registry/list": {"area_id": "kitchen"}}),
        )

        with self.assertRaises(HomeAssistantClientError):
            client.fetch_areas()

    def test_close_closes_websocket_session(self) -> None:
        session = _FakeSession({})
        websocket_session = _FakeWebSocketSession({})
        client = _client(session, websocket_session)

        client.close()

        self.assertTrue(session.closed)
        self.assertTrue(websocket_session.closed)

    def test_service_call_uses_authorised_post_and_entity_body(self) -> None:
        url = "http://ha.local:8123/api/services/light/turn_on"
        session = _FakeSession(
            {url: _FakeResponse([{"entity_id": "light.kitchen", "state": "on"}])}
        )
        client = _client(session)

        result = client.call_service("light", "turn_on", ("light.kitchen",))

        self.assertEqual(result[0]["entity_id"], "light.kitchen")
        self.assertEqual(session.calls[0]["url"], url)
        self.assertEqual(
            session.calls[0]["json"],
            {"entity_id": ["light.kitchen"]},
        )
        self.assertEqual(session.headers["Authorization"], "Bearer secret-token")

    def test_service_call_merges_extra_payload_data(self) -> None:
        url = "http://ha.local:8123/api/services/light/turn_on"
        session = _FakeSession(
            {url: _FakeResponse([{"entity_id": "light.kitchen", "state": "on"}])}
        )
        client = _client(session)

        client.call_service(
            "light",
            "turn_on",
            ("light.kitchen",),
            data={"brightness_pct": 50},
        )

        self.assertEqual(
            session.calls[0]["json"],
            {"entity_id": ["light.kitchen"], "brightness_pct": 50},
        )

    def test_service_http_failure_and_timeout_raise_clean_errors(self) -> None:
        url = "http://ha.local:8123/api/services/switch/turn_off"
        for response in (_FakeResponse([], fail=True), requests.Timeout("slow")):
            with self.subTest(response=type(response).__name__):
                client = _client(_FakeSession({url: response}))
                with self.assertRaises(HomeAssistantClientError):
                    client.call_service(
                        "switch",
                        "turn_off",
                        ("switch.office",),
                    )


if __name__ == "__main__":
    unittest.main()
