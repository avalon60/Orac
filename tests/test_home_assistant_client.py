"""Tests for the Home Assistant API client."""
# Author: Clive Bostock
# Date: 04-Jun-2026
# Description: Verifies Home Assistant REST and WebSocket usage without network calls.

from __future__ import annotations

from pathlib import Path
import sys
import unittest

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
        self.closed = False

    def command(self, command: str):
        self.commands.append(command)
        response = self.responses[command]
        if isinstance(response, BaseException):
            raise response
        return response

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
