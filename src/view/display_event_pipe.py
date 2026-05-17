"""Local display event pipe for Orac visual endpoints."""
# Author: Clive Bostock
# Date: 2026-05-08
# Description: Sends and receives lightweight Orac display state events.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
from typing import Any

from loguru import logger

from lib.config_mgr import ConfigManager
from orac_voice.tts_piper import expand_config_path, resolve_orac_home


DEFAULT_DISPLAY_ENABLED = False
DEFAULT_DISPLAY_AUTO_START = False
DEFAULT_DISPLAY_HOST = "127.0.0.1"
DEFAULT_DISPLAY_PORT = 8766
DEFAULT_DISPLAY_CONNECT_TIMEOUT_SECONDS = 0.05
DEFAULT_DISPLAY_STATE_FILE = "${ORAC_HOME}/var/tmp/orac_display_state.json"
DISPLAY_PROTOCOL_VERSION = 1


DisplayEventHandler = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class DisplayEventConfig:
  """Configuration for the local display event pipe.

  Args:
    enabled: Whether runtime display event emission is enabled.
    auto_start: Whether stack tooling may start the display automatically.
    host: Listener host.
    port: Listener TCP port.
    state_file: Optional latest-state JSON file path.
    connect_timeout_seconds: Sender connection timeout.
  """

  enabled: bool = DEFAULT_DISPLAY_ENABLED
  auto_start: bool = DEFAULT_DISPLAY_AUTO_START
  host: str = DEFAULT_DISPLAY_HOST
  port: int = DEFAULT_DISPLAY_PORT
  state_file: Path | None = None
  connect_timeout_seconds: float = DEFAULT_DISPLAY_CONNECT_TIMEOUT_SECONDS


@dataclass(frozen=True)
class DisplayEvent:
  """JSON-serialisable display event.

  Args:
    event: Event name, such as ``state_changed`` or ``shutdown``.
    state: Optional display state name.
    message: Optional human-readable status message.
    session_id: Optional voice/session identifier.
    turn_id: Optional turn/request identifier.
    created_on: UTC event creation timestamp.
    extra: Additional small JSON-friendly metadata.
  """

  event: str
  state: str | None = None
  message: str | None = None
  session_id: str | None = None
  turn_id: str | None = None
  created_on: str = field(
    default_factory=lambda: datetime.now(timezone.utc).isoformat()
  )
  extra: dict[str, Any] = field(default_factory=dict)
  v: int = DISPLAY_PROTOCOL_VERSION

  def to_dict(self) -> dict[str, Any]:
    """Return a compact JSON-friendly dictionary."""
    data = asdict(self)
    extra = data.pop("extra", {}) or {}
    data.update(extra)
    return {key: value for key, value in data.items() if value is not None}


class DisplayEventSender:
  """Best-effort local display event sender."""

  def __init__(self, config: DisplayEventConfig) -> None:
    """Initialise the sender.

    Args:
      config: Display event pipe configuration.
    """
    self.config = config
    self._last_socket_warning_at = 0.0

  @classmethod
  def from_config(
    cls,
    *,
    config_file_path: Path | None = None,
  ) -> "DisplayEventSender":
    """Create a sender from ``resources/config/orac.ini``."""
    config_path = config_file_path or (
      resolve_orac_home() / "resources" / "config" / "orac.ini"
    )
    config_mgr = ConfigManager(config_file_path=config_path)
    return cls(load_display_event_config(config_mgr))

  def send_state(
    self,
    state: str,
    *,
    message: str | None = None,
    session_id: str | None = None,
    turn_id: str | None = None,
  ) -> None:
    """Send a display state change event."""
    self.send(
      DisplayEvent(
        event="state_changed",
        state=state,
        message=message,
        session_id=session_id,
        turn_id=turn_id,
      )
    )

  def send(
    self,
    event: DisplayEvent | dict[str, Any],
  ) -> None:
    """Send an event to the display, if enabled.

    Args:
      event: Display event dataclass or dictionary.
    """
    if not self.config.enabled:
      return

    payload = event.to_dict() if isinstance(event, DisplayEvent) else dict(event)
    payload.setdefault("v", DISPLAY_PROTOCOL_VERSION)
    self._write_state_file(payload)
    self._send_socket_event(payload)

  def _write_state_file(self, payload: dict[str, Any]) -> None:
    """Write the latest display state for display startup recovery."""
    path = self.config.state_file
    if path is None:
      return
    try:
      path.parent.mkdir(parents=True, exist_ok=True)
      with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
      ) as handle:
        json.dump(payload, handle, ensure_ascii=False)
        handle.write("\n")
        temp_path = Path(handle.name)
      temp_path.replace(path)
    except Exception as exc:
      logger.debug("Unable to write display state file {}: {}", path, exc)

  def _send_socket_event(self, payload: dict[str, Any]) -> None:
    """Best-effort socket send."""
    try:
      wire = json.dumps(payload, ensure_ascii=False) + "\n"
      with socket.create_connection(
        (self.config.host, self.config.port),
        timeout=self.config.connect_timeout_seconds,
      ) as client:
        client.sendall(wire.encode("utf-8"))
    except OSError as exc:
      now = time.monotonic()
      if now - self._last_socket_warning_at > 30.0:
        self._last_socket_warning_at = now
        logger.debug(
          "Orac display listener unavailable at {}:{}: {}",
          self.config.host,
          self.config.port,
          exc,
        )


class DisplayEventServer:
  """Small localhost NDJSON display event server."""

  def __init__(
    self,
    *,
    host: str,
    port: int,
    on_event: DisplayEventHandler,
  ) -> None:
    """Initialise the display event server.

    Args:
      host: Host/interface to bind.
      port: TCP port to bind.
      on_event: Callback for each decoded event.
    """
    self.host = host
    self.port = port
    self.on_event = on_event
    self._stop_requested = threading.Event()
    self._thread: threading.Thread | None = None
    self._server: socket.socket | None = None
    self.bound_port: int | None = None

  @property
  def is_running(self) -> bool:
    """Return whether the server thread is alive."""
    return self._thread is not None and self._thread.is_alive()

  def start(self) -> None:
    """Start the listener thread."""
    if self.is_running:
      return
    self._stop_requested.clear()
    self._thread = threading.Thread(
      target=self._run,
      name="orac-display-event-listener",
      daemon=True,
    )
    self._thread.start()

  def stop(self, *, timeout: float | None = 1.0) -> None:
    """Stop the listener thread."""
    self._stop_requested.set()
    if self._server is not None:
      try:
        self._server.close()
      except OSError:
        pass
    if self._thread is not None:
      self._thread.join(timeout=timeout)
    self._thread = None

  def _run(self) -> None:
    """Run the blocking socket accept loop."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.settimeout(0.2)
    self._server = server
    try:
      server.bind((self.host, self.port))
      self.bound_port = int(server.getsockname()[1])
      server.listen()
      logger.info(
        "Orac display event listener started on {}:{}",
        self.host,
        self.bound_port,
      )
      while not self._stop_requested.is_set():
        try:
          conn, _address = server.accept()
        except socket.timeout:
          continue
        except OSError:
          if self._stop_requested.is_set():
            return
          raise
        with conn:
          self._handle_connection(conn)
    except Exception as exc:
      if not self._stop_requested.is_set():
        logger.warning("Orac display event listener stopped: {}", exc)
    finally:
      try:
        server.close()
      except OSError:
        pass
      self._server = None
      self.bound_port = None

  def _handle_connection(self, conn: socket.socket) -> None:
    """Read and dispatch newline-delimited JSON events."""
    data = b""
    while True:
      chunk = conn.recv(4096)
      if not chunk:
        break
      data += chunk

    for line in data.decode("utf-8", errors="replace").splitlines():
      line = line.strip()
      if not line:
        continue
      try:
        event = json.loads(line)
      except json.JSONDecodeError as exc:
        logger.debug("Ignoring invalid display event JSON: {}", exc)
        continue
      if isinstance(event, dict):
        self.on_event(event)


def load_display_event_config(
  config_mgr: ConfigManager,
) -> DisplayEventConfig:
  """Load display event pipe configuration."""
  orac_home = resolve_orac_home()
  raw_state_file = config_mgr.config_value(
    "display",
    "state_file",
    default=DEFAULT_DISPLAY_STATE_FILE,
  )
  state_file = (
    expand_config_path(raw_state_file, orac_home=orac_home)
    if raw_state_file.strip()
    else None
  )
  return DisplayEventConfig(
    enabled=config_mgr.bool_config_value(
      "display",
      "enabled",
      default=DEFAULT_DISPLAY_ENABLED,
    ),
    auto_start=config_mgr.bool_config_value(
      "display",
      "auto_start",
      default=DEFAULT_DISPLAY_AUTO_START,
    ),
    host=config_mgr.config_value(
      "display",
      "host",
      default=DEFAULT_DISPLAY_HOST,
    ).strip(),
    port=config_mgr.int_config_value(
      "display",
      "port",
      default=DEFAULT_DISPLAY_PORT,
    ),
    state_file=state_file,
    connect_timeout_seconds=float(
      config_mgr.config_value(
        "display",
        "connect_timeout_seconds",
        default=str(DEFAULT_DISPLAY_CONNECT_TIMEOUT_SECONDS),
      )
    ),
  )


def load_latest_state_file(path: Path | None) -> dict[str, Any] | None:
  """Load the latest display state event from disk."""
  if path is None or not path.exists():
    return None
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError) as exc:
    logger.debug("Unable to load display state file {}: {}", path, exc)
    return None
  return data if isinstance(data, dict) else None
