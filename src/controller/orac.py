"""Oracle orchestrator, orac.py (protocol-enabled, non-streaming response)"""
import asyncio
import subprocess
import re
import json
import uuid
import os
import time
import sys
import traceback
from pathlib import Path
from datetime import datetime, timezone

from model.network import OracListener
from model.llm_connector import LMStudioConnector, OllamaConnector
from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from lib.icons import Icons
from lib.logutil import Logger
from model.orac_auth import FrameAuthChain, ZenFrameAuth

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOG_DIR = project_home() / 'logs'
APP_HOME = project_home()
RESOURCES_DIR = APP_HOME / 'resources'
CONFIG_DIR = RESOURCES_DIR / 'config'
CONFIG_FILE_PATH = CONFIG_DIR / 'orac.ini'

conf_manager = ConfigManager(config_file_path=CONFIG_FILE_PATH)
LOG_LEVEL = conf_manager.config_value(section="logging", key="log_level", default='INFO')
logger = Logger(log_file=LOG_DIR / 'orac.log', log_level=LOG_LEVEL)

# Protocol validator (installed from the Orac repo tag)
# Protocol validator: prefer installed package; fall back to local schema if import fails
try:
    from orac_protocol import validate_frame, SCHEMA_VERSION as PROTOCOL_VERSION
except Exception as e:
    logger.log_warning(f"⚠️ Protocol module unavailable; using local schema fallback: {e}")

    try:
        import json
        from jsonschema import Draft202012Validator

        local_schema_path = (APP_HOME / "protocol/orac_protocol/resources/json_schema/protocol.schema.json")
        with local_schema_path.open("rb") as fh:
            # tolerate BOM and stray leading bytes
            raw = fh.read()
            schema_text = raw.decode("utf-8-sig")
            # crude sanitiser: trim to the first '{' and last '}'
            first = schema_text.find("{")
            last = schema_text.rfind("}")
            if first != -1 and last != -1 and last > first:
                schema_text = schema_text[first:last+1]
            schema = json.loads(schema_text)

        _validator = Draft202012Validator(schema)

        def validate_frame(env_obj: dict) -> None:
            _validator.validate(env_obj)

        PROTOCOL_VERSION = schema.get("$id", "local-schema")
        logger.log_info(f"✅ Using local protocol schema at {local_schema_path}")
    except Exception as e2:
        logger.log_warning(f"⚠️ Local schema fallback failed; validation disabled: {e2}")

        def validate_frame(_): ...
        PROTOCOL_VERSION = "unknown"



def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _log_exception(prefix: str, exc: BaseException):
    """Log an exception with full stack trace."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.log_error(f"{prefix}: {exc}\n{tb}")


def system_clock_line(prefs: dict) -> str:
    tz_name = prefs.get("timezone", "Europe/London")
    now_utc = datetime.now(timezone.utc)
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
        tz_name = "UTC"

    now_local = now_utc.astimezone(tz)

    # Oracle-style: DD-MON-YYYY HH24:MI  -> %d-%b-%Y %H:%M (uppercased MON)
    local_str = now_local.strftime("%d-%b-%Y %H:%M").upper()
    utc_iso   = now_utc.isoformat(timespec="seconds").replace("+00:00", "Z")

    # Optional: day of week
    dow = now_local.strftime("%A").upper()

    lines = [
        f"Current time: {utc_iso} (UTC).",
        f"Local time: {local_str} ({tz_name}); day: {dow}.",
    ]

    # If you store a user pref like date_format='DD-MON-YYYY HH24:MI', tell the model:
    if "date_format" in prefs:
        lines.append(f"Use date format {prefs['date_format']}.")

    # If you have a 'force_concise' boolean:
    if prefs.get("force_concise") is True:
        lines.append("Keep answers concise.")

    return "\n".join(lines)


class Orac:
    """
    Orac is the AI orchestrator that routes messages to the LLM and skills system.
    """
    def __init__(self):
        logger.log_info('Instantiating Orac...')
        try:
            self.config_mgr = ConfigManager(config_file_path=CONFIG_FILE_PATH)
            self.llm_service_id = self.config_mgr.config_value('service', 'llm_service_id')
            self.model_name = self.config_mgr.config_value('service', 'default_model_name')
            self.service_url = self.config_mgr.config_value('service', 'service_url')
            self.strip_reasoning_tags = self.config_mgr.config_value(
                'settings', 'strip_reasoning_tags', default="true"
            ).lower() == "true"

            service_map = {
                "ollama": OllamaConnector,
                "lmstudio": LMStudioConnector
            }

            self._validate_or_pull_model()
            try:
                connector_cls = service_map[self.llm_service_id]
            except KeyError:
                message = f"{Icons.error} LLM service not implemented: {self.llm_service_id}"
                logger.log_critical(message)
                raise NotImplementedError(message)

            self.llm = connector_cls(service_url=self.service_url, model_name=self.model_name)

            # --- Auth setup: load secret, nonce store, auth chain -----------------
            secret_path = Path(os.environ.get("ORAC_HMAC_SECRET_FILE", "/run/orac/slave.secret"))
            try:
                self._hmac_secret = secret_path.read_bytes().strip()
            except Exception as e:
                _log_exception(f"{Icons.error} Unable to read HMAC secret at {secret_path}", e)
                raise

            self._seen_nonces: dict[str, int] = {}

            def _nonce_seen_once(nonce: str, ts: int) -> bool:
                # Light pruning for old entries
                if len(self._seen_nonces) > 50000:
                    cutoff = int(time.time()) - 3600
                    for k, v in list(self._seen_nonces.items()):
                        if v < cutoff:
                            self._seen_nonces.pop(k, None)
                if nonce in self._seen_nonces:
                    return False
                self._seen_nonces[nonce] = ts
                return True

            self.auth_chain = FrameAuthChain([
                ZenFrameAuth(shared_secret=self._hmac_secret, skew_secs=300, nonce_seen=_nonce_seen_once),
                # Add more providers here later if needed
            ])

            logger.log_info(f"{Icons.robot} Orac orchestrator initialized with model: {self.model_name}")
            logger.log_info(f"{Icons.settings} Reasoning tags stripped by default: {self.strip_reasoning_tags}")
            logger.log_info(f"{Icons.docs} Protocol version: {PROTOCOL_VERSION}")

        except Exception as e:
            _log_exception("Fatal error during Orac initialization", e)
            raise


    def _validate_or_pull_model(self):
        """Validates that the configured model is available (pulls for Ollama; checks LM Studio)."""
        if self.llm_service_id == "ollama":
            try:
                output = subprocess.check_output(["ollama", "list"], text=True)
                if self.model_name not in output:
                    logger.log_warning(f"{Icons.warn} Model '{self.model_name}' not found in Ollama. Pulling it now...")
                    subprocess.run(["ollama", "pull", self.model_name], check=True)
                    logger.log_info(f"{Icons.tick} Model '{self.model_name}' pulled successfully.")
                else:
                    logger.log_info(f"{Icons.tick} Model '{self.model_name}' is already available in Ollama.")
            except FileNotFoundError as e:
                _log_exception(f"{Icons.error} Ollama not installed or not in PATH", e)
                raise RuntimeError("Ollama is not installed or not in PATH.") from e
            except subprocess.CalledProcessError as e:
                _log_exception(f"{Icons.error} Failed to pull model '{self.model_name}'", e)
                raise RuntimeError(f"Failed to pull model '{self.model_name}': {e}") from e

        elif self.llm_service_id == "lmstudio":
            import requests
            try:
                response = requests.get(f"{self.service_url}/v1/models", timeout=10)
                response.raise_for_status()
                models = response.json().get("data", [])
                available_models = [m["id"] for m in models]
                if self.model_name not in available_models:
                    msg = (
                        f"{Icons.error} Model '{self.model_name}' not loaded in LM Studio at {self.service_url}."
                        f"\n{Icons.right_arrow} Please load it in LM Studio and try again."
                    )
                    logger.log_error(msg)
                    raise RuntimeError(msg)
                else:
                    logger.log_info(f"{Icons.tick} Model '{self.model_name}' is loaded in LM Studio.")
            except requests.exceptions.ConnectionError as e:
                _log_exception(f"{Icons.error} Could not connect to LM Studio server at {self.service_url}", e)
                raise RuntimeError(f"Could not connect to LM Studio server at {self.service_url}.") from e
            except Exception as e:
                _log_exception(f"{Icons.error} Error validating model in LM Studio", e)
                raise RuntimeError(f"Error validating model in LM Studio: {e}") from e
        else:
            msg = f"{Icons.error} Unknown LLM service: {self.llm_service_id}"
            logger.log_error(msg)
            raise RuntimeError(msg)

    def _strip_reasoning_tags(self, text: str) -> str:
        """
        Strips <think>...</think> blocks. If we detect a dangling <think>
        with no closing </think>, treat it as incomplete and drop it entirely.
        """
        if not isinstance(text, str):
            return ""
        if "<think>" in text and "</think>" not in text:
            return ""  # trigger fallback / retry logic upstream
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # === Response builder ======================================================
    def _build_response(self, req_env: dict, content: str, *,
                        stop_reason: str = "stop",
                        prompt_tokens: int = 0,
                        completion_tokens: int = 0) -> dict:
        """Build a protocol-compliant non-streaming response envelope."""
        resp = {
            "v": 1,
            "type": "response",
            "id": new_id("res"),
            "reply_to": req_env.get("id"),
            "ts": iso_now(),
            "route": req_env.get("route", "orac.prompt"),
            "meta": {
                "status": "ok",
                "model": self.model_name,
                "req_id": req_env.get("id"),
            },
            "payload": {
                "content": content,
                "stop_reason": stop_reason,
                "usage": {
                    "prompt_tokens": int(prompt_tokens),
                    "completion_tokens": int(completion_tokens),
                    "total_tokens": int(prompt_tokens) + int(completion_tokens)
                }
            },
            "error": None
        }
        try:
            validate_frame(resp)
        except Exception as e:
            _log_exception("Response failed protocol validation (returning anyway)", e)
        return resp

    async def handle_request(self, message: str) -> str:
        try:
            req_env = json.loads(message)  # strict JSON
        except Exception as e:
            _log_exception("Failed to parse request JSON", e)
            err_env = {
                "v": 1, "type": "response", "id": new_id("res"),
                "reply_to": None, "ts": iso_now(), "route": "orac.prompt",
                "meta": {"status": "error", "model": self.model_name},
                "payload": None, "error": {"code": "BAD_JSON", "message": str(e)}
            }
            return json.dumps(err_env, ensure_ascii=False)

        try:
            # Quick shape check before auth
            if not isinstance(req_env, dict) or req_env.get("type") != "request":
                raise ValueError("invalid request envelope")

            # --- AUTH FIRST ---
            try:
                auth_res = self.auth_chain.authenticate(req_env)
            except Exception as e:
                _log_exception("Authentication chain failed", e)
                raise

            if not auth_res.ok:
                logger.log_warning(f"Unauthorised request: {auth_res.reason}")
                err = {
                    "v": 1, "type": "response", "id": new_id("res"),
                    "reply_to": req_env.get("id"), "ts": iso_now(),
                    "route": req_env.get("route", "orac.prompt"),
                    "meta": {"status": "error", "model": self.model_name, "req_id": req_env.get("id")},
                    "payload": None,
                    "error": {"code": "UNAUTHORISED", "message": auth_res.reason or "unauthorised"}
                }
                return json.dumps(err, ensure_ascii=False)

            # Schema validation after auth
            try:
                validate_frame(req_env)
            except Exception as e:
                _log_exception("Request failed protocol validation", e)
                err = {
                    "v": 1, "type": "response", "id": new_id("res"),
                    "reply_to": req_env.get("id"), "ts": iso_now(),
                    "route": req_env.get("route", "orac.prompt"),
                    "meta": {"status": "error", "model": self.model_name, "req_id": req_env.get("id")},
                    "payload": None,
                    "error": {"code": "INVALID_FRAME", "message": str(e)}
                }
                return json.dumps(err, ensure_ascii=False)

            if req_env.get("route") != "orac.prompt":
                raise ValueError("Unsupported request type/route")

            messages = (req_env.get("payload") or {}).get("messages") or []
            prompt = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "").strip()
            meta = req_env.get("meta") or {}
            show_reasoning = bool(meta.get("show_reasoning", not self.strip_reasoning_tags))
            client = meta.get("client", "unknown")

            logger.log_info(f"{Icons.info} [{client}] user={getattr(auth_res, 'user', 'unknown')} Prompt received")
            logger.log_debug(f"Prompt text: {prompt}")
            logger.log_info(f"meta.show_reasoning={show_reasoning} (strip_reasoning_default={self.strip_reasoning_tags})")

            # === Call backend (non-streaming path) ===
            try:
                raw = self.llm.send_prompt(prompt_type="U", prompt=prompt, stream=False)
            except Exception as e:
                _log_exception("LLM backend call failed", e)
                err = {
                    "v": 1, "type": "response", "id": new_id("res"),
                    "reply_to": req_env.get("id"), "ts": iso_now(), "route": "orac.prompt",
                    "meta": {"status": "error", "model": self.model_name, "req_id": req_env.get("id")},
                    "payload": None,
                    "error": {"code": "LLM_BACKEND_ERROR", "message": str(e)}
                }
                return json.dumps(err, ensure_ascii=False)

            # Normalise: ensure string
            if hasattr(raw, "content"):
                raw = raw.content
            if not isinstance(raw, str):
                raw = str(raw)
            raw = raw.strip()

            # Apply local reasoning-strip unless explicitly requested
            if show_reasoning:
                content = raw
            else:
                stripped = self._strip_reasoning_tags(raw)
                # Fallback: if stripping removed everything, use the raw text
                content = stripped if stripped else raw

            # Final guard: never send empty content
            if not content:
                logger.log_warning("Backend returned empty content after stripping; using friendly fallback.")
                content = "Hello! 👋"

            resp_env = self._build_response(req_env, content, stop_reason="stop",
                                            prompt_tokens=0, completion_tokens=0)

            wire = json.dumps(resp_env, ensure_ascii=False)
            logger.log_debug(f"Returning response frame: {wire[:300]}{'…' if len(wire) > 300 else ''}")
            return wire

        except Exception as e:
            _log_exception("Error while processing request", e)
            err_env = {
                "v": 1, "type": "response", "id": new_id("res"),
                "reply_to": req_env.get("id") if isinstance(req_env, dict) else None,
                "ts": iso_now(), "route": "orac.prompt",
                "meta": {"status": "error", "model": self.model_name},
                "payload": None, "error": {"code": "SERVER_ERROR", "message": str(e)}
            }
            return json.dumps(err_env, ensure_ascii=False)


async def main():
    try:
        orchestrator = Orac()
        listener = OracListener(orchestrator=orchestrator, host="127.0.0.1", port=8765)
        await listener.start_server()
    except Exception as e:
        _log_exception("Fatal in main()", e)
        raise


if __name__ == "__main__":
    # Global safeguards: log ANY uncaught exceptions (sync + asyncio)
    def _global_excepthook(exc_type, exc, tb):
        tb_str = "".join(traceback.format_exception(exc_type, exc, tb))
        logger.log_critical(f"Uncaught exception:\n{tb_str}")

    sys.excepthook = _global_excepthook

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        def _asyncio_exception_handler(loop, context):
            msg = context.get("message") or "Asyncio exception"
            exc = context.get("exception")
            if exc:
                _log_exception(msg, exc)
            else:
                logger.log_error(f"{msg}: {context}")

        loop.set_exception_handler(_asyncio_exception_handler)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.log_warning(f"{Icons.stop} Orac shutting down (KeyboardInterrupt).")
    except Exception as e:
        _log_exception("Uncaught fatal in __main__", e)
        raise
    finally:
        try:
            loop.close()
        except Exception as e:
            _log_exception("Error closing event loop", e)
