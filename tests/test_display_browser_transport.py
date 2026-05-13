"""Tests for the optional Orac browser WebSocket transport."""
# Author: Clive Bostock
# Date: 2026-05-12
# Description: Verifies browser transport handshake and broadcast delivery.

from __future__ import annotations

import base64
import json
from pathlib import Path
import os
import socket
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from view.display_browser_transport import DisplayBrowserTransport


def _free_local_port() -> int:
  """Return a currently free localhost TCP port."""
  try:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
      sock.bind(("127.0.0.1", 0))
      return int(sock.getsockname()[1])
  except PermissionError as exc:
    raise unittest.SkipTest("Local sockets are unavailable in this sandbox") from exc


def _recv_exact(sock: socket.socket, size: int) -> bytes:
  """Receive exactly ``size`` bytes from a socket."""
  chunks: list[bytes] = []
  remaining = size
  while remaining > 0:
    chunk = sock.recv(remaining)
    if not chunk:
      raise ConnectionError("Socket closed before receiving expected bytes.")
    chunks.append(chunk)
    remaining -= len(chunk)
  return b"".join(chunks)


def _recv_until(sock: socket.socket, delimiter: bytes) -> bytes:
  """Receive bytes until ``delimiter`` appears."""
  data = bytearray()
  while delimiter not in data:
    chunk = sock.recv(1024)
    if not chunk:
      raise ConnectionError("Socket closed before handshake completed.")
    data.extend(chunk)
  return bytes(data)


def _connect_websocket(port: int) -> socket.socket:
  """Perform a browser WebSocket handshake against the transport."""
  sock = socket.create_connection(("127.0.0.1", port), timeout=2.0)
  key = base64.b64encode(os.urandom(16)).decode("ascii")
  request = "\r\n".join(
    [
      "GET / HTTP/1.1",
      "Host: 127.0.0.1",
      "Upgrade: websocket",
      "Connection: Upgrade",
      f"Sec-WebSocket-Key: {key}",
      "Sec-WebSocket-Version: 13",
      "",
      "",
    ]
  )
  sock.sendall(request.encode("ascii"))
  response = _recv_until(sock, b"\r\n\r\n")
  if b"101 Switching Protocols" not in response:
    raise AssertionError(response.decode("ascii", errors="replace"))
  return sock


def _read_text_frame(sock: socket.socket) -> str:
  """Read one unmasked server text frame."""
  header = _recv_exact(sock, 2)
  opcode = header[0] & 0x0F
  if opcode != 0x1:
    raise AssertionError(f"Unexpected opcode: {opcode}")

  length = header[1] & 0x7F
  if length == 126:
    length = int.from_bytes(_recv_exact(sock, 2), "big")
  elif length == 127:
    length = int.from_bytes(_recv_exact(sock, 8), "big")

  payload = _recv_exact(sock, length) if length else b""
  return payload.decode("utf-8")


class DisplayBrowserTransportTests(unittest.TestCase):
  """Tests for the browser WebSocket transport."""

  def test_buttons_visible_config_is_sent_on_connect(self) -> None:
    """The transport announces UI button visibility to new clients."""
    transport = DisplayBrowserTransport(
      host="127.0.0.1",
      port=_free_local_port(),
      state_file=None,
      buttons_visible=True,
    )
    transport.start()
    try:
      sock = _connect_websocket(transport.bound_port or transport.port)
      try:
        received = json.loads(_read_text_frame(sock))
      finally:
        sock.close()
    finally:
      transport.stop()

    self.assertEqual(received["event"], "ui_config")
    self.assertTrue(received["buttons_visible"])

  def test_broadcast_delivers_text_frame_to_browser_client(self) -> None:
    """The transport broadcasts JSON payloads to connected browsers."""
    transport = DisplayBrowserTransport(
      host="127.0.0.1",
      port=_free_local_port(),
      state_file=None,
    )
    transport.start()
    try:
      sock = _connect_websocket(transport.bound_port or transport.port)
      try:
        payload = {
          "v": 1,
          "event": "state_changed",
          "state": "thinking",
          "message": "Thinking",
        }
        transport.broadcast(payload)
        received = json.loads(_read_text_frame(sock))
      finally:
        sock.close()
    finally:
      transport.stop()

    self.assertEqual(received["event"], "state_changed")
    self.assertEqual(received["state"], "thinking")
    self.assertEqual(received["message"], "Thinking")


if __name__ == "__main__":
  unittest.main()
