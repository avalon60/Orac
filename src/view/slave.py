"""
Slave (slave.py): Strict protocol-only TCP console client for Orac orchestrator. Named after the computer onboard Scorpio,
the successor ship to Liberator.
"""

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
from lib.fsutils import project_home
from lib.config_mgr import ConfigManager
# Icons / logging
from lib.icons import Icons
os.environ["LOGURU_AUTOINIT"] = "0"  # must be set before importing our logger
from lib.logutil import Logger
LOG_DIR = project_home() / 'logs'

PROG_NAME = Path(__file__).name
APP_HOME = project_home()
CONFIG_FILE_PATH = APP_HOME / 'resources' / 'config' / 'orac.ini'
conf_manager = ConfigManager(config_file_path=CONFIG_FILE_PATH)
LOG_LEVEL = conf_manager.config_value(section="logging", key="log_level", default='INFO')
logger = Logger(log_file=LOG_DIR / 'local_client.log', log_level=LOG_LEVEL)

LLM_TIMEOUT = int(conf_manager.config_value(section="client", key="llm_timeout", default="90"))
SHOW_TIMESTAMP = conf_manager.bool_config_value(section="client", key="show_timestamp", default=True)
print(f'LLM_TIMEOUT: {LLM_TIMEOUT} seconds')


# Protocol validator (installed from Orac repo tag)
try:
    from orac_protocol import validate_frame, SCHEMA_VERSION as PROTOCOL_VERSION
except Exception:  # if not installed yet
    def validate_frame(_): ...
    PROTOCOL_VERSION = "unknown"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
WRAP_WIDTH = 100

# Local preference for showing <think>…</think> blocks
SHOW_REASONING = False

# ---- HMAC secret + signing helpers ------------------------------------------

SECRET_FILE = Path(os.environ.get("ORAC_HMAC_SECRET_FILE", "/run/orac/slave.secret"))

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

def ts_prefix() -> str:
    """Return [HH:MM:SS] prefix if SHOW_TIMESTAMP is enabled."""
    if SHOW_TIMESTAMP:
        return f"[{datetime.now().strftime('%H:%M:%S')}] "
    return ""

def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

# IMPORTANT: load secret once at module import (fail-fast if missing)
SECRET = load_secret()
CALLING_USER = os.getenv("ORAC_CALLING_USER") or getuser()  # allow override for service accounts

def build_prompt_request(message_text: str) -> dict:
    """
    Build a strict protocol-compliant 'request' envelope for route 'orac.prompt'.
    Streaming off; channel=text. Adds meta.auth (hmac-v1).
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
        "session_id": "local",
        "stream": False,
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

async def tcp_client(host=DEFAULT_HOST, port=DEFAULT_PORT):
    logger.log_info(f"{Icons.rocket} Connecting to Orac at {host}:{port} (protocol {PROTOCOL_VERSION}) ...")

    try:
        reader, writer = await asyncio.open_connection(host, port)
        print(f"{Icons.robot} Connected. Type 'exit' or 'quit' to quit.\n")
        logger.log_info(f"{Icons.robot} Connected.")

        while True:
            user_input = input(f"{ts_prefix()}{Icons.right_arrow} You: ").strip()
            if not user_input:
                logger.log_debug("Empty input received. Skipping send.")
                continue

            if user_input.lower() in {"exit", "quit"}:
                print(f"{Icons.wave} Exiting client session.")
                logger.log_info("Client session exited by user.")
                break

            # --- Send strict protocol request (with meta.auth) ---
            req_env = build_prompt_request(user_input)
            wire = json.dumps(req_env, ensure_ascii=False) + "\n"
            writer.write(wire.encode("utf-8"))
            await writer.drain()

            # --- Read one protocol response line (server is protocol-only single-line) ---
            try:
                resp_bytes = await asyncio.wait_for(reader.readline(), timeout=LLM_TIMEOUT)
            except asyncio.TimeoutError:
                logger.log_error("Timeout waiting for server response.")
                print(f"{Icons.error} [protocol error] server timeout\n")
                # Optional: reconnect here to avoid late-reply bleed (uncomment if desired)
                # try:
                #     writer.close()
                #     await writer.wait_closed()
                # finally:
                #     reader, writer = await asyncio.open_connection(host, port)
                #     logger.log_info(f"{Icons.robot} Reconnected after timeout.")
                continue

            response_text = resp_bytes.decode("utf-8", errors="replace").strip()
            logger.log_debug(f"Raw response from Orac: {response_text!r}")

            # --- Parse strictly as JSON object ---
            try:
                env = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.log_error(f"Invalid JSON from server: {e} | raw={response_text!r}")
                print(f"{Icons.error} [invalid protocol frame] see log\n")
                continue

            if not isinstance(env, dict) or "v" not in env:
                logger.log_error("Non-envelope frame received (missing 'v' or not an object).")
                print(f"{Icons.error} [invalid protocol frame] see log\n")
                continue

            # --- Validate envelope (warn if server drifts) ---
            try:
                validate_frame(env)
            except Exception as e:
                logger.log_warning(f"Server frame failed protocol validation: {e}")

            # --- Envelope type must be a response for this non-streaming client ---
            if env.get("type") != "response":
                logger.log_error(f"Unexpected envelope type: {env.get('type')}")
                print(f"{ts_prefix()}{Icons.error} [invalid protocol frame] unexpected envelope type\n")
                continue

            # --- If the server returned an error, surface it cleanly and continue ---
            err_obj = env.get("error")
            if isinstance(err_obj, dict) and err_obj:
                code = err_obj.get("code", "SERVER_ERROR")
                msg  = err_obj.get("message", "Unknown error")
                print(f"{ts_prefix()}{Icons.error} [server error] {code}: {msg}\n")
                details = err_obj.get("details")
                if isinstance(details, dict) and details:
                    logger.log_error(f"Server error details: {details}")
                continue

            # --- Normal response: extract payload.content (schema-compliant) ---
            payload = env.get("payload")
            content = payload.get("content") if isinstance(payload, dict) else None
            if not isinstance(content, str) or not content.strip():
                logger.log_error("Envelope missing payload.content or it is empty.")
                print(f"{ts_prefix()}{Icons.error} [invalid protocol frame] missing payload.content\n")
                continue

            # --- Render to console ---
            clean = strip_reasoning_tags(content)
            wrapped = textwrap.fill(clean, width=WRAP_WIDTH)
            print(f"{ts_prefix()}{Icons.robot} Orac: {wrapped}\n")

    except ConnectionRefusedError:
        print(f"{Icons.error} Could not connect to Orac at {host}:{port}. Is it running?")
        logger.log_error(f"Could not connect to Orac at {host}:{port}.")
    except KeyboardInterrupt:
        print(f"\n{Icons.wave} Client terminated by user.")
        logger.log_warning("Client session terminated by user (KeyboardInterrupt).")
    except Exception as e:
        print(f"{Icons.critical} Unexpected error: {e}")
        logger.log_critical(f"Unexpected error in tcp_client: {e}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
            logger.log_info("Connection to Orac closed.")
        except NameError:
            logger.log_warning("Writer was not created; skipping close.")

if __name__ == "__main__":
    asyncio.run(tcp_client())
