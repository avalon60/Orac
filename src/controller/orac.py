"""Oracle orchestrator, orac.py (protocol-enabled, non-streaming response)"""
import asyncio
import subprocess
import re
import json
import uuid
import os
import time
from pathlib import Path
from datetime import datetime, timezone

from model.network import OracListener
from model.llm_connector import LMStudioConnector, OllamaConnector
from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from lib.icons import Icons
from lib.logutil import Logger
from model.orac_auth import FrameAuthChain, ZenFrameAuth
logger = Logger()

# Protocol validator (installed from the Orac repo tag)
try:
    from orac_protocol import validate_frame, SCHEMA_VERSION as PROTOCOL_VERSION
except Exception:
    def validate_frame(_): ...
    PROTOCOL_VERSION = "unknown"

APP_HOME = project_home()
RESOURCES_DIR = APP_HOME / 'resources'
CONFIG_DIR = RESOURCES_DIR / 'config'
CONFIG_FILE_PATH = CONFIG_DIR / 'orac.ini'


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class Orac:
    """
    Orac is the AI orchestrator that routes messages to the LLM and skills system.
    """
    def __init__(self):
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

        try:
            self._validate_or_pull_model()
            self.llm = service_map[self.llm_service_id](service_url=self.service_url, model_name=self.model_name)
        except KeyError:
            message = f"{Icons.error} LLM service not implemented: {self.llm_service_id}"
            raise NotImplementedError(message)

        # --- Auth setup: load secret, nonce store, auth chain -----------------
        secret_path = Path(os.environ.get("ORAC_HMAC_SECRET_FILE", "/run/orac/slave.secret"))
        try:
            self._hmac_secret = secret_path.read_bytes().strip()
        except Exception as e:
            raise RuntimeError(f"{Icons.error} Unable to read HMAC secret at {secret_path}: {e}")

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

        print(f"{Icons.robot} Orac orchestrator initialized with model: {self.model_name}")
        print(f"{Icons.settings} Reasoning tags stripped by default: {self.strip_reasoning_tags}")
        print(f"{Icons.docs} Protocol version: {PROTOCOL_VERSION}")

    def _validate_or_pull_model(self):
        """Validates that the configured model is available (pulls for Ollama; checks LM Studio)."""
        if self.llm_service_id == "ollama":
            try:
                output = subprocess.check_output(["ollama", "list"], text=True)
                if self.model_name not in output:
                    print(f"{Icons.warn} Model '{self.model_name}' not found in Ollama. Pulling it now...")
                    subprocess.run(["ollama", "pull", self.model_name], check=True)
                    print(f"{Icons.tick} Model '{self.model_name}' pulled successfully.")
                else:
                    print(f"{Icons.tick} Model '{self.model_name}' is already available in Ollama.")
            except FileNotFoundError:
                raise RuntimeError(f"{Icons.error} Ollama is not installed or not in PATH.")
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"{Icons.error} Failed to pull model '{self.model_name}': {e}")

        elif self.llm_service_id == "lmstudio":
            import requests
            try:
                response = requests.get(f"{self.service_url}/v1/models")
                response.raise_for_status()
                models = response.json().get("data", [])
                available_models = [m["id"] for m in models]
                if self.model_name not in available_models:
                    raise RuntimeError(
                        f"{Icons.error} Model '{self.model_name}' not loaded in LM Studio at {self.service_url}."
                        f"\n{Icons.right_arrow} Please load it in LM Studio and try again."
                    )
                else:
                    print(f"{Icons.tick} Model '{self.model_name}' is loaded in LM Studio.")
            except requests.exceptions.ConnectionError:
                raise RuntimeError(f"{Icons.error} Could not connect to LM Studio server at {self.service_url}.")
            except Exception as e:
                raise RuntimeError(f"{Icons.error} Error validating model in LM Studio: {e}")
        else:
            raise RuntimeError(f"{Icons.error} Unknown LLM service: {self.llm_service_id}")

    def _strip_reasoning_tags(self, text: str) -> str:
        """Strips <think>...</think> blocks from the text if enabled."""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    def _build_response(self, req_env: dict, content: str) -> dict:
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
                "latency_ms": 0  # optional; fill if you measure
            },
            "payload": {
                "content": content,
                "stop_reason": "stop",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            },
            "error": None
        }
        try:
            validate_frame(resp)
        except Exception as e:
            # Log but still return JSON so the client can show something
            logger.log_warning(f"Response failed protocol validation (returning anyway): {e}")
        return resp

    async def handle_request(self, message: str) -> str:
        try:
            req_env = json.loads(message)  # strict JSON

            # Quick shape check before auth
            if not isinstance(req_env, dict) or req_env.get("type") != "request":
                raise ValueError("invalid request envelope")

            # --- AUTH FIRST ---
            auth_res = self.auth_chain.authenticate(req_env)
            if not auth_res.ok:
                err = {
                    "v": 1, "type": "response", "id": new_id("res"),
                    "reply_to": req_env.get("id"), "ts": iso_now(),
                    "route": req_env.get("route", "orac.prompt"),
                    "meta": {"status": "error", "model": self.model_name},
                    "payload": None,
                    "error": {"code": "UNAUTHORISED", "message": auth_res.reason or "unauthorised"}
                }
                return json.dumps(err, ensure_ascii=False)

            # Schema validation after auth (so we can reject unauth early)
            validate_frame(req_env)
            if req_env.get("route") != "orac.prompt":
                raise ValueError("Unsupported request type/route")

            messages = (req_env.get("payload") or {}).get("messages") or []
            prompt = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "").strip()
            meta = req_env.get("meta") or {}
            show_reasoning = bool(meta.get("show_reasoning", not self.strip_reasoning_tags))
            client = meta.get("client", "unknown")

            user = auth_res.user or "unknown"
            print(f"{Icons.info} [{client}] user={user} Prompt received: {prompt}")

            raw = self.llm.send_prompt(prompt_type="U", prompt=prompt)
            content = raw if show_reasoning else self._strip_reasoning_tags(raw)

            resp_env = self._build_response(req_env, content)

            wire = json.dumps(resp_env, ensure_ascii=False)
            logger.log_debug(f"Returning response frame: {wire[:300]}{'…' if len(wire) > 300 else ''}")
            return wire

        except Exception as e:
            logger.log_error(f"Error while processing request: {e}")
            err_env = {
                "v": 1, "type": "response", "id": new_id("res"),
                "reply_to": None, "ts": iso_now(), "route": "orac.prompt",
                "meta": {"status": "error", "model": self.model_name},
                "payload": None, "error": {"code": "SERVER_ERROR", "message": str(e)}
            }
            return json.dumps(err_env, ensure_ascii=False)


async def main():
    orchestrator = Orac()
    listener = OracListener(orchestrator=orchestrator, host="127.0.0.1", port=8765)
    await listener.start_server()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"{Icons.stop} Orac shutting down.")
