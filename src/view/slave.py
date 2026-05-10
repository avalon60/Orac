"""
Slave (slave.py): Strict protocol-only TCP console client for Orac orchestrator. Named after the computer onboard Scorpio,
the successor ship to Liberator.
"""

# Author: Clive Bostock
# Date: 2026-04-25
# Description: Strict protocol-only TCP console client for Orac with persistent local input history.

import asyncio
import json
import os
import re
import textwrap
import uuid
import hmac
import base64
import hashlib
import secrets
import time
from pathlib import Path
from datetime import datetime, timezone
from getpass import getuser

try:
    import readline
except ImportError:  # pragma: no cover - platform-dependent availability
    readline = None

from lib.fsutils import project_home
from lib.config_mgr import ConfigManager
# Icons / logging
from lib.icons import Icons
import shutil

os.environ["LOGURU_AUTOINIT"] = "0"  # must be set before importing our logger
from lib.logutil import Logger
LOG_DIR = project_home() / 'logs'

PROG_NAME = Path(__file__).name
APP_HOME = project_home()
CONFIG_FILE_PATH = APP_HOME / 'resources' / 'config' / 'orac.ini'
conf_manager = ConfigManager(config_file_path=CONFIG_FILE_PATH)
LOG_LEVEL = conf_manager.config_value(section="logging", key="log_level", default='INFO')
logger = Logger(log_file=LOG_DIR / 'local_client.log', log_level=LOG_LEVEL, inc_std_err=False)

LLM_TIMEOUT = int(conf_manager.config_value(section="client", key="llm_timeout", default="90"))
SHOW_TIMESTAMP = conf_manager.bool_config_value(section="client", key="show_timestamp", default=True)
HISTORY_FILE = LOG_DIR / "slave_history"
HISTORY_LENGTH = 500
logger.log_debug(f'LLM_TIMEOUT: {LLM_TIMEOUT} seconds')


# Protocol validator (installed from Orac repo tag)
try:
    from orac_protocol import validate_frame, SCHEMA_VERSION as PROTOCOL_VERSION
except Exception:  # if not installed yet
    def validate_frame(_): ...
    PROTOCOL_VERSION = "unknown"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
WRAP_WIDTH = 100
STREAM_EVENT_TYPES = {
    "stream_start",
    "text_delta",
    "text_chunk",
    "stream_end",
    "stream_error",
    "stream_cancelled",
    "tts_playback_started",
    "tts_playback_finished",
    "tts_playback_cancelled",
    "tts_playback_error",
    "voice_turn_complete",
}

# Local preference for showing <think>…</think> blocks
SHOW_REASONING = False

# ---- HMAC secret + signing helpers ------------------------------------------

SECRET_FILE = Path(os.environ.get("ORAC_HMAC_SECRET_FILE", "/run/orac/slave.secret"))

def get_wrap_width(default=100) -> int:
    try:
        cols = shutil.get_terminal_size(fallback=(default, 24)).columns
        return max(40, min(cols, 160))
    except Exception:
        return default

_CODE_FENCE_RE = re.compile(r"```.*?```", flags=re.DOTALL)
_STREAM_THINK_RE = re.compile(r"<think>.*?</think>", flags=re.DOTALL)

def render_for_console(text: str, width: int) -> str:
    """
    Preserve code fences and deliberate newlines.
    - Segments inside ```...``` are emitted verbatim.
    - Non-code segments are wrapped paragraph-by-paragraph.
    """
    out: list[str] = []
    pos = 0
    for m in _CODE_FENCE_RE.finditer(text):
        # preface
        pre = text[pos:m.start()]
        if pre:
            out.append(_wrap_paragraphs(pre, width))
        # code block verbatim
        out.append(m.group(0))
        pos = m.end()
    tail = text[pos:]
    if tail:
        out.append(_wrap_paragraphs(tail, width))
    return "\n".join(out)

def _wrap_paragraphs(chunk: str, width: int) -> str:
    # split on blank lines to keep paragraph boundaries
    paras = re.split(r"\n\s*\n", chunk.strip("\n"))
    wrapped_paras = []
    for p in paras:
        # If the paragraph looks like preformatted (leading 4 spaces or tabs), keep as-is
        if re.match(r"^(?:[ \t]{4,}|\t)", p) or "  \n" in p:
            wrapped_paras.append(p)
            continue
        # Wrap line-by-line if paragraph contains many hard newlines (lists)
        lines = p.splitlines() if "\n" in p else [p]
        out_lines = []
        for ln in lines:
            # Don’t wrap empty lines
            if not ln.strip():
                out_lines.append("")
                continue
            # Keep common list prefixes / bullets indentation
            if re.match(r"^\s*([-*•]|\d+\.)\s+", ln):
                filled = textwrap.fill(
                    ln,
                    width=width,
                    subsequent_indent=" " * (len(ln) - len(ln.lstrip())),
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            else:
                filled = textwrap.fill(
                    ln,
                    width=width,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            out_lines.append(filled)
        wrapped_paras.append("\n".join(out_lines))
    return "\n\n".join(wrapped_paras)


def load_secret() -> bytes:
    try:
        return SECRET_FILE.read_bytes().strip()
    except Exception as e:
        raise RuntimeError(f"Unable to load Orac secret from {SECRET_FILE}: {e}")

def canonical_json(obj) -> bytes:
    """Stable JSON bytes for hashing/signing."""
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")

def sign_auth(secret: bytes, user: str, route: str, payload: dict) -> dict:
    """
    Build the meta.auth dict for the current frame.
    Signature input: user|ts|nonce|route|sha256(payload)
    """
    ts = int(time.time())
    nonce = secrets.token_hex(16)
    payload_hash = hashlib.sha256(canonical_json(payload)).hexdigest()
    to_sign = f"{user}|{ts}|{nonce}|{route}|{payload_hash}".encode("utf-8")
    sig = base64.b64encode(hmac.new(secret, to_sign, hashlib.sha256).digest()).decode("ascii")
    return {"scheme": "hmac-v1", "user": user, "ts": ts, "nonce": nonce, "sig": sig}

# ---- existing helpers --------------------------------------------------------

def strip_reasoning_tags(text: str) -> str:
    """Remove <think>…</think> content unless SHOW_REASONING is True."""
    if SHOW_REASONING:
        return text
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def strip_reasoning_tags_from_delta(text: str) -> str:
    """Remove complete reasoning blocks without trimming stream spacing."""
    if SHOW_REASONING:
        return text
    return _STREAM_THINK_RE.sub("", text)

def ts_prefix() -> str:
    """Return [HH:MM:SS] prefix if SHOW_TIMESTAMP is enabled."""
    if SHOW_TIMESTAMP:
        return f"[{datetime.now().strftime('%H:%M:%S')}] "
    return ""

def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def load_input_history() -> None:
    """Load local CLI history when readline support is available."""
    if readline is None:
        logger.log_debug("readline not available; input history disabled.")
        return

    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        readline.set_history_length(HISTORY_LENGTH)
        if HISTORY_FILE.exists():
            readline.read_history_file(HISTORY_FILE)
    except Exception as exc:
        logger.log_warning(f"Unable to load input history from {HISTORY_FILE}: {exc}")


def save_input_history() -> None:
    """Persist local CLI history when readline support is available."""
    if readline is None:
        return

    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        readline.set_history_length(HISTORY_LENGTH)
        readline.write_history_file(HISTORY_FILE)
    except Exception as exc:
        logger.log_warning(f"Unable to save input history to {HISTORY_FILE}: {exc}")


def remember_history_entry(user_input: str) -> None:
    """Add a non-empty command to the in-memory readline history."""
    if readline is None or not user_input:
        return

    try:
        last_entry = None
        current_length = readline.get_current_history_length()
        if current_length > 0:
            last_entry = readline.get_history_item(current_length)
        if user_input != last_entry:
            readline.add_history(user_input)
    except Exception as exc:
        logger.log_warning(f"Unable to update input history: {exc}")

# IMPORTANT: load secret once at module import (fail-fast if missing)
SECRET = load_secret()
CALLING_USER = os.getenv("ORAC_CALLING_USER") or getuser()  # allow override for service accounts
CLIENT_SESSION_ID = f"slave-{CALLING_USER}-{uuid.uuid4().hex[:12]}"

def build_prompt_request(message_text: str, *, session_id: str | None = None) -> dict:
    """
    Build a strict protocol-compliant 'request' envelope for route 'orac.prompt'.
    Streaming on; channel=text. Adds meta.auth (hmac-v1).
    """
    route = "orac.prompt"
    payload = {
        "messages": [
            {"role": "system", "content": "you are orac."},
            {"role": "user", "content": message_text},
        ]
    }

    # Meta WITHOUT auth first (auth signs over route + payload)
    meta = {
        "client": "slave",
        "session_id": session_id or CLIENT_SESSION_ID,
        "stream": True,
        "channel": "text",
        "show_reasoning": SHOW_REASONING,
    }
    auth = sign_auth(SECRET, CALLING_USER, route, payload)
    meta["auth"] = auth

    env = {
        "v": 1,
        "type": "request",
        "id": new_id("req"),
        "ts": iso_now(),
        "route": route,
        "meta": meta,
        "payload": payload,
        "error": None,
    }
    # Validate our own outbound frame; if this fails, it's our bug.
    try:
        validate_frame(env)
    except Exception as e:
        logger.log_critical(f"Client built an invalid protocol frame: {e}")
    return env


def build_voice_cancel_request(
    *,
    session_id: str,
    turn_id: str | None = None,
    scope: str = "active",
    reason: str = "barge-in",
) -> dict:
    """Build an authenticated request to cancel local voice output."""
    route = "orac.voice.cancel"
    payload = {
        "session_id": session_id,
        "scope": scope,
        "reason": reason,
    }
    if turn_id:
        payload["turn_id"] = turn_id

    meta = {
        "client": "slave",
        "session_id": session_id,
        "stream": False,
        "channel": "control",
    }
    meta["auth"] = sign_auth(SECRET, CALLING_USER, route, payload)

    env = {
        "v": 1,
        "type": "request",
        "id": new_id("req"),
        "ts": iso_now(),
        "route": route,
        "meta": meta,
        "payload": payload,
        "error": None,
    }
    try:
        validate_frame(env)
    except Exception as e:
        logger.log_critical(f"Client built an invalid voice cancel frame: {e}")
    return env


def _render_user_registration_notice(meta: dict | None, notice_shown: bool) -> bool:
    """Render a one-time anonymous-user notice from response metadata."""
    if notice_shown or not isinstance(meta, dict):
        return notice_shown

    if meta.get("user_registration") == "anonymous":
        print(f"{ts_prefix()}{Icons.robot} Orac: You are connected as an anonymous user.\n")
        logger.log_info("Displayed anonymous-user notice from response metadata.")
        return True

    return notice_shown

async def tcp_client(host=DEFAULT_HOST, port=DEFAULT_PORT):
    logger.log_info(f"{Icons.rocket} Connecting to Orac at {host}:{port} (protocol {PROTOCOL_VERSION}) ...")
    load_input_history()

    try:
        reader, writer = await asyncio.open_connection(host, port)
        print(f"{Icons.robot} Connected. Type 'exit' or 'quit' to quit.\n")
        logger.log_info(f"{Icons.robot} Connected.")
        anonymous_notice_shown = False

        while True:
            raw_input_value = input(f"{ts_prefix()}{Icons.right_arrow} You: ")
            user_input = raw_input_value.strip()
            if not user_input:
                logger.log_debug("Empty input received. Skipping send.")
                continue

            remember_history_entry(user_input)

            if user_input.lower() in {"exit", "quit"}:
                print(f"{Icons.wave} Exiting client session.")
                logger.log_info("Client session exited by user.")
                break

            # --- Send strict protocol request (with meta.auth) ---
            req_env = build_prompt_request(user_input)
            wire = json.dumps(req_env, ensure_ascii=False) + "\n"
            writer.write(wire.encode("utf-8"))
            await writer.drain()

            stream_rendered = False
            stream_finished = False
            stream_error_seen = False

            while True:
                try:
                    resp_bytes = await asyncio.wait_for(
                        reader.readline(),
                        timeout=LLM_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.log_error("Timeout waiting for server response.")
                    print(f"{Icons.error} [protocol error] server timeout\n")
                    break

                response_text = resp_bytes.decode("utf-8", errors="replace").strip()
                logger.log_debug(f"Raw response from Orac: {response_text!r}")

                try:
                    env = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.log_error(
                        f"Invalid JSON from server: {e} | raw={response_text!r}"
                    )
                    print(f"{Icons.error} [invalid protocol frame] see log\n")
                    break

                if not isinstance(env, dict) or "v" not in env:
                    logger.log_error(
                        "Non-envelope frame received (missing 'v' or not an object)."
                    )
                    print(f"{Icons.error} [invalid protocol frame] see log\n")
                    break

                try:
                    validate_frame(env)
                except Exception as e:
                    logger.log_warning(f"Server frame failed protocol validation: {e}")

                frame_type = env.get("type")
                anonymous_notice_shown = _render_user_registration_notice(
                    env.get("meta"),
                    anonymous_notice_shown,
                )

                if frame_type in STREAM_EVENT_TYPES:
                    err_obj = env.get("error")
                    if isinstance(err_obj, dict) and err_obj:
                        stream_error_seen = True
                        code = err_obj.get("code", "SERVER_ERROR")
                        msg = err_obj.get("message", "Unknown error")
                        if stream_rendered:
                            print()
                        print(f"{ts_prefix()}{Icons.error} [stream error] {code}: {msg}\n")
                        continue

                    payload = env.get("payload")
                    payload = payload if isinstance(payload, dict) else {}

                    if frame_type == "stream_start":
                        print(f"{ts_prefix()}{Icons.robot} Orac: ", end="", flush=True)
                        stream_rendered = True
                    elif frame_type == "text_delta":
                        if not stream_rendered:
                            print(
                                f"{ts_prefix()}{Icons.robot} Orac: ",
                                end="",
                                flush=True,
                            )
                            stream_rendered = True
                        delta = payload.get("delta", "")
                        print(
                            strip_reasoning_tags_from_delta(str(delta)),
                            end="",
                            flush=True,
                        )
                    elif frame_type == "text_chunk":
                        logger.log_debug(
                            f"Speech text chunk received: {payload.get('chunk', '')!r}"
                        )
                    elif frame_type == "stream_end":
                        stream_finished = True
                        if stream_rendered:
                            print()
                    elif frame_type == "stream_cancelled":
                        stream_finished = True
                        if stream_rendered:
                            print()
                        print(f"{ts_prefix()}{Icons.warn} [stream cancelled]\n")
                    elif frame_type == "voice_turn_complete":
                        stream_finished = True
                        if stream_rendered:
                            print()
                    continue

                if frame_type != "response":
                    logger.log_error(f"Unexpected envelope type: {frame_type}")
                    print(
                        f"{ts_prefix()}{Icons.error} "
                        "[invalid protocol frame] unexpected envelope type\n"
                    )
                    break

                err_obj = env.get("error")
                if isinstance(err_obj, dict) and err_obj:
                    code = err_obj.get("code", "SERVER_ERROR")
                    msg = err_obj.get("message", "Unknown error")
                    if not stream_error_seen:
                        print(f"{ts_prefix()}{Icons.error} [server error] {code}: {msg}\n")
                    details = err_obj.get("details")
                    if isinstance(details, dict) and details:
                        logger.log_error(f"Server error details: {details}")
                    break

                payload = env.get("payload")
                content = payload.get("content") if isinstance(payload, dict) else None
                if not isinstance(content, str) or not content.strip():
                    logger.log_error("Envelope missing payload.content or it is empty.")
                    print(
                        f"{ts_prefix()}{Icons.error} "
                        "[invalid protocol frame] missing payload.content\n"
                    )
                    break

                if stream_rendered or stream_finished:
                    print()
                    break

                clean = strip_reasoning_tags(content)
                width = get_wrap_width(WRAP_WIDTH)
                rendered = render_for_console(clean, width)
                first_prefix = f"{ts_prefix()}{Icons.robot} Orac: "
                lines = rendered.splitlines(True)
                if lines:
                    print(first_prefix + lines[0], end="")
                    for ln in lines[1:]:
                        print(ln, end="")
                    print()
                    print()
                else:
                    print(first_prefix + "\n")
                break

# --- Main ---

    except ConnectionRefusedError:
        print(f"{Icons.error} Could not connect to Orac at {host}:{port}. Is it running?")
        logger.log_error(f"Could not connect to Orac at {host}:{port}.")
    except KeyboardInterrupt:
        print(f"\n{Icons.wave} Client terminated by user.")
        logger.log_warning("Client session terminated by user (KeyboardInterrupt).")
    except EOFError:
        print(f"\n{Icons.wave} Client session closed.")
        logger.log_info("Client session terminated by EOF.")
    except Exception as e:
        print(f"{Icons.critical} Unexpected error: {e}")
        logger.log_critical(f"Unexpected error in tcp_client: {e}")
    finally:
        try:
            save_input_history()
            writer.close()
            await writer.wait_closed()
            logger.log_info("Connection to Orac closed.")
        except NameError:
            save_input_history()
            logger.log_warning("Writer was not created; skipping close.")

if __name__ == "__main__":
    asyncio.run(tcp_client())
