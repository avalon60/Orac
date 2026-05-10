"""Tests for the optional Orac display event pipe."""
# Author: Clive Bostock
# Date: 2026-05-08
# Description: Verifies display event serialisation, config, and socket delivery.

from __future__ import annotations

import json
from pathlib import Path
import socket
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from lib.config_mgr import ConfigManager
from view.display_event_pipe import DisplayEvent
from view.display_event_pipe import DisplayEventConfig
from view.display_event_pipe import DisplayEventSender
from view.display_event_pipe import DisplayEventServer
from view.display_event_pipe import load_display_event_config
from view.display_event_pipe import load_latest_state_file


def _free_local_port() -> int:
  """Return a currently free localhost TCP port."""
  try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
      sock.bind(("127.0.0.1", 0))
      return int(sock.getsockname()[1])
  except PermissionError as exc:
    raise unittest.SkipTest("Local sockets are unavailable in this sandbox") from exc


class DisplayEventPipeTests(unittest.TestCase):
  """Tests for local display event helpers."""

  def test_display_event_serialises_compact_payload(self) -> None:
    """DisplayEvent flattens extra metadata and omits null values."""
    event = DisplayEvent(
      event="state_changed",
      state="speaking",
      message="Speaking",
      session_id="session-1",
      extra={"score": 0.92},
    )

    payload = event.to_dict()

    self.assertEqual(payload["event"], "state_changed")
    self.assertEqual(payload["state"], "speaking")
    self.assertEqual(payload["score"], 0.92)
    self.assertNotIn("turn_id", payload)

  def test_disabled_sender_does_not_touch_socket_or_state_file(self) -> None:
    """Disabled display emission is a true no-op."""
    with tempfile.TemporaryDirectory() as temp_dir:
      state_file = Path(temp_dir) / "state.json"
      sender = DisplayEventSender(
        DisplayEventConfig(enabled=False, state_file=state_file)
      )

      with patch("socket.create_connection") as create_connection:
        sender.send_state("listening", message="Listening")

      create_connection.assert_not_called()
      self.assertFalse(state_file.exists())

  def test_enabled_sender_writes_latest_state_file(self) -> None:
    """Enabled emission writes the latest state file even without a display."""
    with tempfile.TemporaryDirectory() as temp_dir:
      state_file = Path(temp_dir) / "state.json"
      sender = DisplayEventSender(
        DisplayEventConfig(
          enabled=True,
          host="127.0.0.1",
          port=_free_local_port(),
          state_file=state_file,
          connect_timeout_seconds=0.01,
        )
      )

      with patch("socket.create_connection", side_effect=OSError("closed")):
        sender.send_state("thinking", message="Thinking", turn_id="turn-1")

      payload = load_latest_state_file(state_file)
      self.assertIsNotNone(payload)
      self.assertEqual(payload["state"], "thinking")
      self.assertEqual(payload["message"], "Thinking")
      self.assertEqual(payload["turn_id"], "turn-1")

  def test_socket_server_receives_ndjson_event(self) -> None:
    """The sender can deliver one event to the local display server."""
    received: list[dict[str, object]] = []
    server = DisplayEventServer(
      host="127.0.0.1",
      port=_free_local_port(),
      on_event=received.append,
    )
    server.start()
    try:
      time.sleep(0.05)
      sender = DisplayEventSender(
        DisplayEventConfig(
          enabled=True,
          host="127.0.0.1",
          port=server.port,
          state_file=None,
          connect_timeout_seconds=0.2,
        )
      )

      sender.send_state("listening", message="Listening for wake word")

      deadline = time.monotonic() + 2.0
      while not received and time.monotonic() < deadline:
        time.sleep(0.02)
    finally:
      server.stop()

    self.assertEqual(received[0]["event"], "state_changed")
    self.assertEqual(received[0]["state"], "listening")
    self.assertEqual(received[0]["message"], "Listening for wake word")

  def test_display_config_loads_optional_defaults(self) -> None:
    """Display config values are loaded from orac.ini style config."""
    with tempfile.TemporaryDirectory() as temp_dir:
      config_path = Path(temp_dir) / "orac.ini"
      state_file = Path(temp_dir) / "display.json"
      config_path.write_text(
        "\n".join(
          [
            "[display]",
            "enabled = true",
            "auto_start = false",
            "host = 127.0.0.1",
            "port = 8766",
            f"state_file = {state_file}",
            "connect_timeout_seconds = 0.25",
          ]
        ),
        encoding="utf-8",
      )

      config = load_display_event_config(ConfigManager(config_path))

      self.assertTrue(config.enabled)
      self.assertFalse(config.auto_start)
      self.assertEqual(config.port, 8766)
      self.assertEqual(config.state_file, state_file)
      self.assertEqual(config.connect_timeout_seconds, 0.25)

  def test_latest_state_file_rejects_non_object_json(self) -> None:
    """The state-file loader only accepts JSON objects."""
    with tempfile.TemporaryDirectory() as temp_dir:
      state_file = Path(temp_dir) / "state.json"
      state_file.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")

      self.assertIsNone(load_latest_state_file(state_file))


if __name__ == "__main__":
  unittest.main()
