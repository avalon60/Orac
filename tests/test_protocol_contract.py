"""Contract tests for Orac protocol frame shapes.

# Author: Clive Bostock
# Date: 2026-05-24
# Description: Captures current golden protocol frames for streaming, TTS,
#   and voice cancellation behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from jsonschema.exceptions import ValidationError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
PROTOCOL_ROOT = PROJECT_ROOT / "protocol"
for root in (SRC_ROOT, PROTOCOL_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


if "langchain_openai" not in sys.modules:
    stub_module = types.ModuleType("langchain_openai")

    class _StubChatOpenAI:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def invoke(self, prompt):
            return prompt

    stub_module.ChatOpenAI = _StubChatOpenAI
    sys.modules["langchain_openai"] = stub_module


if "oracledb" not in sys.modules:
    stub_oracledb = types.ModuleType("oracledb")

    class _StubConnection:
        pass

    class _StubDatabaseError(Exception):
        pass

    stub_oracledb.Connection = _StubConnection
    stub_oracledb.DatabaseError = _StubDatabaseError
    stub_oracledb.NUMBER = object()
    sys.modules["oracledb"] = stub_oracledb


from controller.orac import Orac
from orac_protocol import validate_frame
from orac_voice.voice_events import VoiceTtsPlaybackCancelled
from orac_voice.voice_events import VoiceTtsPlaybackError
from orac_voice.voice_events import VoiceTtsPlaybackFinished
from orac_voice.voice_events import VoiceTtsPlaybackStarted
from orac_voice.voice_events import VoiceTurnComplete


def _request_env() -> dict:
    """Return a minimal request envelope used as the stream reply target."""
    return {
        "v": 1,
        "type": "request",
        "id": "req-contract",
        "ts": "2026-05-24T10:00:00.000Z",
        "route": "orac.prompt",
        "meta": {"client": "contract-test", "personality_code": "DEFAULT"},
        "payload": {"messages": [{"role": "user", "content": "Hello"}]},
        "error": None,
    }


class ProtocolContractTests(unittest.TestCase):
    """Golden contract tests for frames emitted by the Orac runtime."""

    def _orac_stub(self) -> Orac:
        orchestrator = Orac.__new__(Orac)
        orchestrator.model_name = "test-model"
        return orchestrator

    def test_runtime_stream_frames_match_current_wire_contract(self) -> None:
        """Runtime stream frames validate and expose consumed compatibility fields."""
        orchestrator = self._orac_stub()
        req_env = _request_env()
        cases = [
            (
                "stream_start",
                {"content_type": "text", "voice_session_id": "voice-1", "turn_id": "turn-1"},
                None,
            ),
            (
                "retrieval_start",
                {"mode": "internet", "reason": "explicit_freshness_request"},
                None,
            ),
            (
                "retrieval_query",
                {"query": "latest Oracle Database version", "provider": "searxng"},
                None,
            ),
            (
                "retrieval_fetch_start",
                {"source_count": 4},
                None,
            ),
            (
                "retrieval_fetch_complete",
                {"fetched_count": 4, "usable_source_count": 2},
                None,
            ),
            (
                "retrieval_complete",
                {"source_count": 4, "usable_source_count": 2},
                None,
            ),
            (
                "retrieval_failed",
                {"mode": "internet", "reason": "no_usable_sources"},
                None,
            ),
            (
                "retrieval_skipped",
                {"mode": "internet", "reason": "retrieval_disabled"},
                None,
            ),
            ("text_delta", {"delta": "Hel"}, None),
            (
                "text_chunk",
                {
                    "chunk": "Hello there.",
                    "session_id": "session-1",
                    "voice_session_id": "voice-1",
                    "turn_id": "turn-1",
                },
                None,
            ),
            (
                "stream_end",
                {
                    "stop_reason": "stop",
                    "voice_session_id": "voice-1",
                    "turn_id": "turn-1",
                    "usage": {
                        "prompt_tokens": 3,
                        "completion_tokens": 4,
                        "total_tokens": 7,
                    },
                },
                None,
            ),
            (
                "stream_error",
                {"voice_session_id": "voice-1", "turn_id": "turn-1"},
                {"code": "LLM_BACKEND_ERROR", "message": "backend failed"},
            ),
            (
                "stream_cancelled",
                {
                    "reason": "barge-in",
                    "voice_session_id": "voice-1",
                    "turn_id": "turn-1",
                },
                None,
            ),
        ]

        for frame_type, payload, error in cases:
            with self.subTest(frame_type=frame_type):
                frame = orchestrator._build_stream_event(
                    req_env,
                    frame_type,
                    payload=payload,
                    model_name="test-model",
                    error=error,
                )

                self.assertEqual(frame["v"], 1)
                self.assertEqual(frame["type"], frame_type)
                self.assertEqual(frame["reply_to"], req_env["id"])
                self.assertEqual(frame["route"], "orac.prompt")
                self.assertEqual(frame["meta"]["model"], "test-model")
                self.assertEqual(frame["meta"]["req_id"], req_env["id"])
                self.assertEqual(frame["payload"], payload)
                self.assertEqual(frame["error"], error)
                validate_frame(frame)

        delta_frame = orchestrator._build_stream_event(
            req_env,
            "text_delta",
            payload={"delta": "Hel"},
            model_name="test-model",
        )
        chunk_frame = orchestrator._build_stream_event(
            req_env,
            "text_chunk",
            payload={
                "chunk": "Hello there.",
                "session_id": "session-1",
                "voice_session_id": "voice-1",
                "turn_id": "turn-1",
            },
            model_name="test-model",
        )
        end_frame = orchestrator._build_stream_event(
            req_env,
            "stream_end",
            payload={
                "stop_reason": "stop",
                "voice_session_id": "voice-1",
                "turn_id": "turn-1",
                "usage": {
                    "prompt_tokens": 3,
                    "completion_tokens": 4,
                    "total_tokens": 7,
                },
            },
            model_name="test-model",
        )

        self.assertEqual(delta_frame["payload"]["delta"], "Hel")
        self.assertEqual(chunk_frame["payload"]["chunk"], "Hello there.")
        self.assertEqual(chunk_frame["payload"]["voice_session_id"], "voice-1")
        self.assertEqual(chunk_frame["payload"]["turn_id"], "turn-1")
        self.assertEqual(end_frame["payload"]["usage"]["total_tokens"], 7)
        self.assertEqual(end_frame["meta"]["model"], "test-model")

    def test_normal_response_frame_still_validates(self) -> None:
        """Normal prompt responses remain schema-valid after stream alignment."""
        orchestrator = self._orac_stub()
        response = orchestrator._build_response(
            _request_env(),
            "Hello.",
            prompt_tokens=2,
            completion_tokens=3,
            model_name="test-model",
        )

        validate_frame(response)
        self.assertEqual(response["type"], "response")
        self.assertEqual(response["meta"]["model"], "test-model")
        self.assertEqual(response["payload"]["usage"]["total_tokens"], 5)

    def test_schema_accepts_legacy_stream_delta_alias(self) -> None:
        """The schema documents content_delta as a legacy alias for delta."""
        frame = {
            "v": 1,
            "type": "text_delta",
            "id": "evt-legacy-delta",
            "reply_to": "req-contract",
            "ts": "2026-05-24T10:00:00.000Z",
            "route": "orac.prompt",
            "meta": {"status": "ok", "model": "test-model"},
            "payload": {"content_delta": "Hel"},
            "error": None,
        }

        validate_frame(frame)

    def test_runtime_rejects_invalid_stream_frame_payloads(self) -> None:
        """Runtime stream builders do not emit frames that fail schema validation."""
        orchestrator = self._orac_stub()

        with patch("controller.orac._log_exception") as log_exception:
            with self.assertRaises((ValueError, ValidationError)):
                orchestrator._build_stream_event(
                    _request_env(),
                    "text_delta",
                    payload={},
                    model_name="test-model",
                )

        log_exception.assert_called_once()

    def test_tts_playback_frames_validate_against_protocol_schema(self) -> None:
        """TTS playback lifecycle frames are schema-valid protocol frames."""
        orchestrator = self._orac_stub()
        cases = [
            (
                "tts_playback_started",
                VoiceTtsPlaybackStarted(
                    session_id="voice-1",
                    turn_id="turn-1",
                    utterance_id="utt-1",
                ),
            ),
            (
                "tts_playback_finished",
                VoiceTtsPlaybackFinished(
                    session_id="voice-1",
                    turn_id="turn-1",
                    utterance_id="utt-1",
                ),
            ),
            (
                "tts_playback_cancelled",
                VoiceTtsPlaybackCancelled(
                    session_id="voice-1",
                    turn_id="turn-1",
                    utterance_id="utt-1",
                    reason="barge-in",
                ),
            ),
            (
                "tts_playback_error",
                VoiceTtsPlaybackError(
                    session_id="voice-1",
                    turn_id="turn-1",
                    utterance_id="utt-1",
                    message="playback failed",
                ),
            ),
            (
                "voice_turn_complete",
                VoiceTurnComplete(
                    session_id="voice-1",
                    turn_id="turn-1",
                    reason="completed",
                ),
            ),
        ]

        for frame_type, event in cases:
            with self.subTest(frame_type=frame_type):
                frame = orchestrator._build_voice_playback_event_frame(
                    event,
                    frame_type=frame_type,
                )

                validate_frame(frame)
                self.assertEqual(frame["type"], frame_type)
                self.assertEqual(frame["payload"]["turn_id"], "turn-1")
                self.assertIn("timestamp", frame["payload"])

    def test_voice_cancel_request_and_response_validate_against_protocol_schema(self) -> None:
        """Voice cancellation request/response frames preserve the control contract."""
        orchestrator = self._orac_stub()
        orchestrator._voice_cancelled_turns = set()
        orchestrator._tts_worker = None
        orchestrator._tts_coalescer = None
        orchestrator.cancel_voice_turn = lambda session_id, turn_id: 2
        req_env = {
            "v": 1,
            "type": "request",
            "id": "req-cancel",
            "ts": "2026-05-24T10:00:00.000Z",
            "route": "orac.voice.cancel",
            "meta": {},
            "payload": {
                "session_id": "voice-1",
                "turn_id": "turn-1",
                "scope": "turn",
                "reason": "barge-in",
            },
            "error": None,
        }

        validate_frame(req_env)
        response = json.loads(orchestrator._handle_voice_cancel_request(req_env))

        validate_frame(response)
        self.assertEqual(response["route"], "orac.voice.cancel")
        self.assertEqual(response["reply_to"], "req-cancel")
        self.assertEqual(response["payload"], {"cancelled": True, "discarded": 2})
        self.assertIn(("voice-1", "turn-1"), orchestrator._voice_cancelled_turns)

    def test_voice_cancel_all_request_can_omit_session_id(self) -> None:
        """Scope all supports global cancellation without a session id."""
        req_env = {
            "v": 1,
            "type": "request",
            "id": "req-cancel-all",
            "ts": "2026-05-24T10:00:00.000Z",
            "route": "orac.voice.cancel",
            "meta": {},
            "payload": {
                "scope": "all",
                "reason": "shutdown",
            },
            "error": None,
        }

        validate_frame(req_env)

    def test_invalid_frame_type_is_rejected(self) -> None:
        """Unknown frame types are outside the protocol boundary."""
        frame = {
            "v": 1,
            "type": "stream_delta",
            "id": "evt-invalid",
            "ts": "2026-05-24T10:00:00.000Z",
            "route": "orac.prompt",
            "payload": {"delta": "Hel"},
            "error": None,
        }

        with self.assertRaises(ValueError):
            validate_frame(frame)

    def test_missing_required_envelope_fields_are_rejected(self) -> None:
        """The route/type/id/ts envelope structure remains mandatory."""
        frame = {
            "v": 1,
            "type": "text_delta",
            "id": "evt-missing-route",
            "payload": {"delta": "Hel"},
            "error": None,
        }

        with self.assertRaises(ValueError):
            validate_frame(frame)

    def test_malformed_voice_cancel_request_is_rejected(self) -> None:
        """Active voice cancellation requires a session id."""
        frame = {
            "v": 1,
            "type": "request",
            "id": "req-bad-cancel",
            "ts": "2026-05-24T10:00:00.000Z",
            "route": "orac.voice.cancel",
            "meta": {},
            "payload": {
                "scope": "active",
                "reason": "barge-in",
            },
            "error": None,
        }

        with self.assertRaises(ValueError):
            validate_frame(frame)

    def test_malformed_stream_end_usage_metadata_is_rejected(self) -> None:
        """Usage metadata is optional, but strict when present."""
        frame = {
            "v": 1,
            "type": "stream_end",
            "id": "evt-bad-usage",
            "reply_to": "req-contract",
            "ts": "2026-05-24T10:00:00.000Z",
            "route": "orac.prompt",
            "meta": {"status": "ok", "model": "test-model"},
            "payload": {
                "stop_reason": "stop",
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 2,
                    "total_tokens": "3",
                },
            },
            "error": None,
        }

        with self.assertRaises(ValueError):
            validate_frame(frame)


if __name__ == "__main__":
    unittest.main()
