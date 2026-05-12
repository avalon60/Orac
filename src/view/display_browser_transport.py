#!/usr/bin/env python3
# Author: Clive Bostock
# Date: 2026-05-12
# Description: Provides a localhost WebSocket transport for Orac display events.
"""Browser WebSocket transport for Orac display events.

This module mirrors the existing Orac display event payloads to browser
clients over a small localhost WebSocket server. It is intentionally thin and
does not own Orac state or turn logic.
"""

from __future__ import annotations

import asyncio
from base64 import b64encode
import hashlib
import json
from pathlib import Path
import struct
import threading
from typing import Any

from loguru import logger

from view.display_event_pipe import DisplayEventSender
from view.display_event_pipe import load_latest_state_file


DEFAULT_BROWSER_HOST = "127.0.0.1"
DEFAULT_BROWSER_PORT = 8767
WEBSOCKET_MAGIC_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

CLIENT_CLOSE_OPCODE = 0x8
CLIENT_PING_OPCODE = 0x9
CLIENT_PONG_OPCODE = 0xA
SERVER_TEXT_OPCODE = 0x1
SERVER_PONG_OPCODE = 0xA
SERVER_CLOSE_OPCODE = 0x8


class DisplayBrowserTransport:
  """Small browser WebSocket transport for Orac display events."""

  def __init__(
    self,
    *,
    host: str = DEFAULT_BROWSER_HOST,
    port: int = DEFAULT_BROWSER_PORT,
    state_file: Path | None = None,
    buttons_visible: bool = False,
  ) -> None:
    """Initialise the transport.

    Args:
      host: Host/interface to bind.
      port: Browser WebSocket port to bind.
      state_file: Optional latest display state file for startup recovery.
      buttons_visible: Whether to expose the optional browser UI buttons.
    """
    self.host = host
    self.port = port
    self.state_file = state_file
    self.buttons_visible = buttons_visible
    self.bound_port: int | None = None
    self._clients: set[asyncio.StreamWriter] = set()
    self._loop: asyncio.AbstractEventLoop | None = None
    self._server: asyncio.base_events.Server | None = None
    self._thread: threading.Thread | None = None
    self._stop_requested = threading.Event()
    self._ready = threading.Event()
    self._start_error: BaseException | None = None
    self._latest_payload: dict[str, Any] | None = load_latest_state_file(
      state_file
    )

  @property
  def is_running(self) -> bool:
    """Return whether the transport thread is alive."""
    return self._thread is not None and self._thread.is_alive()

  def start(self) -> None:
    """Start the WebSocket transport in the background."""
    if self.is_running:
      return

    self._stop_requested.clear()
    self._ready.clear()
    self._start_error = None
    self._thread = threading.Thread(
      target=self._run,
      name="orac-display-browser-transport",
      daemon=True,
    )
    self._thread.start()

    if not self._ready.wait(timeout=5.0):
      self.stop()
      raise TimeoutError("Timed out starting the Orac browser transport.")

    if self._start_error is not None:
      error = self._start_error
      self.stop()
      raise RuntimeError("Unable to start the Orac browser transport.") from error

  def stop(self, *, timeout: float | None = 1.0) -> None:
    """Stop the WebSocket transport."""
    self._stop_requested.set()
    loop = self._loop
    server = self._server
    if loop is not None and server is not None:
      loop.call_soon_threadsafe(server.close)
    if self._thread is not None:
      self._thread.join(timeout=timeout)
    self._thread = None
    self._loop = None
    self._server = None
    self.bound_port = None
    self._clients.clear()

  def broadcast(self, payload: dict[str, Any]) -> None:
    """Broadcast one Orac display payload to connected browsers."""
    if self._stop_requested.is_set():
      return

    self._latest_payload = dict(payload)
    loop = self._loop
    if loop is None:
      return

    try:
      future = asyncio.run_coroutine_threadsafe(
        self._broadcast_payload(dict(payload)),
        loop,
      )
      future.add_done_callback(self._log_broadcast_result)
    except RuntimeError as exc:
      logger.debug("Unable to schedule browser broadcast: {}", exc)

  def _run(self) -> None:
    """Run the transport event loop."""
    try:
      asyncio.run(self._serve())
    except asyncio.CancelledError:
      pass
    except Exception as exc:
      self._start_error = exc
      self._ready.set()
      if not self._stop_requested.is_set():
        logger.warning("Orac browser transport stopped: {}", exc)

  async def _serve(self) -> None:
    """Start the WebSocket server and serve browser clients."""
    self._loop = asyncio.get_running_loop()
    DisplayEventSender.set_browser_broadcaster(self.broadcast)
    try:
      self._server = await asyncio.start_server(
        self._handle_connection,
        host=self.host,
        port=self.port,
        reuse_address=True,
      )
      sockets = self._server.sockets or []
      if sockets:
        self.bound_port = int(sockets[0].getsockname()[1])
      logger.info(
        "Orac browser transport started on ws://{}:{}",
        self.host,
        self.bound_port or self.port,
      )
      self._ready.set()
      await self._server.serve_forever()
    finally:
      self._ready.set()
      DisplayEventSender.clear_browser_broadcaster()
      if self._server is not None:
        self._server.close()
        try:
          await self._server.wait_closed()
        except Exception:
          pass
      self._server = None
      self._loop = None

  async def _handle_connection(
    self,
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
  ) -> None:
    """Accept one browser connection and stream display payloads."""
    peer = writer.get_extra_info("peername")
    try:
      headers = await self._read_handshake(reader)
      await self._send_handshake(writer, headers)
      self._clients.add(writer)
      logger.debug("Browser connected to Orac transport: {}", peer)
      await self._send_ui_config(writer)
      await self._send_latest_snapshot(writer)
      await self._consume_client_frames(reader, writer)
    except Exception as exc:
      if not self._stop_requested.is_set():
        logger.debug("Browser connection dropped: {}", exc)
    finally:
      self._clients.discard(writer)
      try:
        writer.close()
        await writer.wait_closed()
      except Exception:
        pass
      logger.debug("Browser disconnected from Orac transport: {}", peer)

  async def _read_handshake(self, reader: asyncio.StreamReader) -> dict[str, str]:
    """Read and validate a WebSocket upgrade request."""
    _request_line = await reader.readline()
    if not _request_line:
      raise ConnectionError("Browser closed before sending a handshake.")

    headers: dict[str, str] = {}
    while True:
      line = await reader.readline()
      if line in {b"", b"\r\n", b"\n"}:
        break
      text = line.decode("latin-1").rstrip("\r\n")
      if ":" not in text:
        continue
      name, value = text.split(":", 1)
      headers[name.strip().lower()] = value.strip()

    upgrade = headers.get("upgrade", "").lower()
    connection = headers.get("connection", "").lower()
    key = headers.get("sec-websocket-key")
    version = headers.get("sec-websocket-version")
    if "websocket" not in upgrade or "upgrade" not in connection:
      raise ConnectionError("Browser request did not ask for WebSocket upgrade.")
    if key is None:
      raise ConnectionError("Browser request did not include Sec-WebSocket-Key.")
    if version != "13":
      raise ConnectionError("Unsupported WebSocket version.")
    return headers

  async def _send_handshake(
    self,
    writer: asyncio.StreamWriter,
    headers: dict[str, str],
  ) -> None:
    """Send the WebSocket handshake response."""
    key = headers["sec-websocket-key"]
    accept = b64encode(
      hashlib.sha1(
        f"{key}{WEBSOCKET_MAGIC_GUID}".encode("ascii")
      ).digest()
    ).decode("ascii")
    response = (
      "HTTP/1.1 101 Switching Protocols\r\n"
      "Upgrade: websocket\r\n"
      "Connection: Upgrade\r\n"
      f"Sec-WebSocket-Accept: {accept}\r\n"
      "\r\n"
    )
    writer.write(response.encode("ascii"))
    await writer.drain()

  async def _send_latest_snapshot(self, writer: asyncio.StreamWriter) -> None:
    """Send the latest known state snapshot to one browser client."""
    if self._latest_payload is None:
      return
    await self._send_text(writer, json.dumps(self._latest_payload, ensure_ascii=False))

  async def _send_ui_config(self, writer: asyncio.StreamWriter) -> None:
    """Send browser-only UI configuration to one browser client."""
    payload = {
      "v": 1,
      "event": "ui_config",
      "buttons_visible": self.buttons_visible,
    }
    await self._send_text(writer, json.dumps(payload, ensure_ascii=False))

  async def _broadcast_payload(self, payload: dict[str, Any]) -> None:
    """Broadcast one payload to every connected browser client."""
    if not self._clients:
      return

    message = json.dumps(payload, ensure_ascii=False)
    dead_clients: list[asyncio.StreamWriter] = []
    for writer in list(self._clients):
      try:
        await self._send_text(writer, message)
      except Exception:
        dead_clients.append(writer)

    for writer in dead_clients:
      self._clients.discard(writer)
      try:
        writer.close()
        await writer.wait_closed()
      except Exception:
        pass

  async def _consume_client_frames(
    self,
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
  ) -> None:
    """Consume browser frames until the client disconnects."""
    while not self._stop_requested.is_set():
      try:
        opcode, payload = await self._read_frame(reader)
      except (asyncio.IncompleteReadError, ConnectionError, OSError):
        return

      if opcode == CLIENT_CLOSE_OPCODE:
        await self._send_close(writer)
        return
      if opcode == CLIENT_PING_OPCODE:
        await self._send_frame(writer, SERVER_PONG_OPCODE, payload)
      elif opcode == CLIENT_PONG_OPCODE:
        continue

  async def _read_frame(self, reader: asyncio.StreamReader) -> tuple[int, bytes]:
    """Read one masked WebSocket frame from a browser client."""
    first_two = await reader.readexactly(2)
    first_byte, second_byte = first_two
    opcode = first_byte & 0x0F
    masked = bool(second_byte & 0x80)
    length = second_byte & 0x7F

    if length == 126:
      length = struct.unpack("!H", await reader.readexactly(2))[0]
    elif length == 127:
      length = struct.unpack("!Q", await reader.readexactly(8))[0]

    mask = b""
    if masked:
      mask = await reader.readexactly(4)

    payload = await reader.readexactly(length) if length else b""
    if masked and payload:
      payload = bytes(
        byte ^ mask[index % 4]
        for index, byte in enumerate(payload)
      )
    return opcode, payload

  async def _send_text(self, writer: asyncio.StreamWriter, text: str) -> None:
    """Send a text frame to one browser client."""
    await self._send_frame(writer, SERVER_TEXT_OPCODE, text.encode("utf-8"))

  async def _send_close(self, writer: asyncio.StreamWriter) -> None:
    """Send a close frame to one browser client."""
    await self._send_frame(writer, SERVER_CLOSE_OPCODE, b"")

  async def _send_frame(
    self,
    writer: asyncio.StreamWriter,
    opcode: int,
    payload: bytes,
  ) -> None:
    """Send one unmasked WebSocket frame to the browser."""
    first_byte = 0x80 | (opcode & 0x0F)
    length = len(payload)
    header = bytearray([first_byte])

    if length < 126:
      header.append(length)
    elif length < 65536:
      header.append(126)
      header.extend(struct.pack("!H", length))
    else:
      header.append(127)
      header.extend(struct.pack("!Q", length))

    writer.write(bytes(header) + payload)
    await writer.drain()

  @staticmethod
  def _log_broadcast_result(future: asyncio.Future[Any]) -> None:
    """Log any exception raised while broadcasting to browsers."""
    try:
      future.result()
    except asyncio.CancelledError:
      return
    except BaseException as exc:
      logger.debug("Browser broadcast failed: {}", exc)
