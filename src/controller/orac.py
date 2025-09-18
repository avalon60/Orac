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
from zoneinfo import ZoneInfo

from model.network import OracListener
from model.llm_connector import LMStudioConnector, OllamaConnector
from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from lib.icons import Icons
from lib.logutil import Logger
from model.orac_auth import FrameAuthChain, ZenFrameAuth
from model.context_manager import OracContextManager
from lib.session_manager import DBSession
from lib.user_security import UserSecurity

# --- Paths / Config -----------------------------------------------------------
LOG_DIR = project_home() / "logs"
APP_HOME = project_home()
RESOURCES_DIR = APP_HOME / "resources"
CONFIG_DIR = RESOURCES_DIR / "config"
CONFIG_FILE_PATH = CONFIG_DIR / "orac.ini"
ORACLE_HOME = os.environ.get("ORACLE_HOME")
TNS_ADMIN = RESOURCES_DIR / "tns_admin"

conf_manager = ConfigManager(config_file_path=CONFIG_FILE_PATH)
LOG_LEVEL = conf_manager.config_value(section="logging", key="log_level", default="INFO")
logger = Logger(log_file=LOG_DIR / "orac.log", log_level=LOG_LEVEL)
logger.log_info(f"TNS_ADMIN={TNS_ADMIN}")

# --- Protocol validator (prefer package, fallback to local schema) -----------
try:
    from orac_protocol import validate_frame, SCHEMA_VERSION as PROTOCOL_VERSION
except Exception as e:
    logger.log_warning(f"⚠️ Protocol module unavailable; using local schema fallback: {e}")
    try:
        import json as _json_for_schema
        from jsonschema import Draft202012Validator

        local_schema_path = APP_HOME / "protocol/orac_protocol/resources/json_schema/protocol.schema.json"
        with local_schema_path.open("rb") as fh:
            raw = fh.read()
            schema_text = raw.decode("utf-8-sig")
            first = schema_text.find("{")
            last = schema_text.rfind("}")
            if first != -1 and last != -1 and last > first:
                schema_text = schema_text[first:last + 1]
            schema = _json_for_schema.loads(schema_text)

        _validator = Draft202012Validator(schema)

        def validate_frame(env_obj: dict) -> None:
            _validator.validate(env_obj)

        PROTOCOL_VERSION = schema.get("$id", "local-schema")
        logger.log_info(f"✅ Using local protocol schema at {local_schema_path}")
    except Exception as e2:
        logger.log_warning(f"⚠️ Local schema fallback failed; validation disabled: {e2}")

        def validate_frame(_): ...
        PROTOCOL_VERSION = "unknown"

# --- Debug dump helper (module-level so it's always available) ----------------
def _dump_debug_blob(name: str, content: str) -> None:
    """
    Always dump a debug blob to a file so we can inspect it even when log level hides DEBUG.
    Writes to logs/_debug/{name}-{ts}.txt and logs/_debug/latest-{name}.txt
    """
    try:
        dbg_dir = LOG_DIR / "_debug"
        dbg_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path_ts = dbg_dir / f"{name}-{ts}.txt"
        path_latest = dbg_dir / f"latest-{name}.txt"
        with path_ts.open("w", encoding="utf-8") as fh:
            fh.write(content)
        with path_latest.open("w", encoding="utf-8") as fh:
            fh.write(content)
        logger.log_info(f"{Icons.info} Debug dump written: {path_ts} (latest: {path_latest})")
    except Exception as e:
        _log_exception("Failed writing debug blob", e)

# --- Small utils --------------------------------------------------------------
def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _log_exception(prefix: str, exc: BaseException):
    """Log an exception with full stack trace."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.log_error(f"{prefix}: {exc}\n{tb}")


def system_clock_line(prefs: dict) -> str:
    tz_name = (prefs or {}).get("timezone", "Europe/London")
    now_utc = datetime.now(timezone.utc)
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = ZoneInfo("UTC")
        tz_name = "UTC"

    now_local = now_utc.astimezone(tz)
    local_str = now_local.strftime("%d-%b-%Y %H:%M").upper()
    utc_iso = now_utc.isoformat(timespec="seconds").replace("+00:00", "Z")
    dow = now_local.strftime("%A").upper()

    lines = [
        f"Current time: {utc_iso} (UTC).",
        f"Local time: {local_str} ({tz_name}); day: {dow}.",
    ]
    if "date_format" in (prefs or {}):
        lines.append(f"Use date format {prefs['date_format']}.")
    if (prefs or {}).get("force_concise") is True:
        lines.append("Keep answers concise.")
    return "\n".join(lines)

# --- System primer (module-level, used both inline and for first system turn) -
def _orac_system_primer(meta: dict) -> str:
    """
    Single source of truth for Orac's persona, language policy, and safety rails.
    """
    lang_pref = (meta or {}).get("reply_language", "English")
    return (
        "SYSTEM POLICY — ORAC PERSONA:\n"
        "- Your name is Orac. Never claim to be DeepSeek, OpenAI, or any other vendor model.\n"
        "- Be concise, helpful, and neutral.\n"
        f"- Reply in {lang_pref} unless the user's message is clearly in another language; "
        "in that case, reply in the user's language.\n"
        "- The 'Recent exchange' below contains the COMPLETE conversation history for this session.\n"
        "- You MUST use information the user has voluntarily shared in this conversation to answer their questions.\n"
        "- When asked about personal details (name, location, preferences, etc.), check the conversation history first.\n"
        "- If the user previously mentioned a fact in this conversation, reference it directly.\n"
        "- Only say you don't know if the information was never mentioned in this conversation.\n"
        "- Do not invoke privacy restrictions for information the user has already shared with you.\n"
        "- Do not invent facts or claim long-term memory beyond what is shown.\n"
        "- Do not include <think>…</think> or similar tags in your replies.\n"
    )



# ==============================================================================
# Orac Orchestrator
# ==============================================================================
class Orac:
    """
    Orac is the AI orchestrator that routes messages to the LLM and skills system.
    """
    def __init__(self):
        logger.log_info("Instantiating Orac...")
        try:
            self.config_mgr = ConfigManager(config_file_path=CONFIG_FILE_PATH)
            self.llm_service_id = self.config_mgr.config_value("service", "llm_service_id")
            self.model_name = self.config_mgr.config_value("service", "default_model_name")
            self.service_url = self.config_mgr.config_value("service", "service_url")
            self.enable_prompt_dump = self.config_mgr.bool_config_value("context", "enable_prompt_dump", default=False)
            self.strip_reasoning_tags = (
                self.config_mgr.config_value("settings", "strip_reasoning_tags", default="true").lower() == "true"
            )
            self._history_turn_pairs = int(
                self.config_mgr.config_value("context", "history_turn_pairs", default="6")
            )
            self._reply_language = self.config_mgr.config_value("context", "reply_language", default="English")

            # Configurable conversation timeout (minutes -> seconds) – kept for future use
            conv_timeout_minutes = int(
                self.config_mgr.config_value("context", "conversation_timeout", default="60")
            )
            self._conversation_timeout_secs = max(0, conv_timeout_minutes * 60)

            service_map = {
                "ollama": OllamaConnector,
                "lmstudio": LMStudioConnector,
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
            ])

            project_id = conf_manager.config_value(section="global", key="project_identifier", default="Orac")
            user_sec = UserSecurity(project_identifier=project_id, resource_type="dsn")
            self._user, self._password, self._dsn = user_sec.named_connection_creds(connection_name="orac-service")

            # Initialize the database session
            self.db_session = DBSession(
                wallet_zip_path="",
                verbose=True,
                user=self._user,
                password=self._password,
                dsn=self._dsn,
                config_dir=TNS_ADMIN,
            )

            # Context manager + pruning policy
            self.ctx = OracContextManager(self.db_session)
            self._keep_messages = int(self.config_mgr.config_value("context", "keep_messages", default="200"))
            self._prune_after_turns = int(self.config_mgr.config_value("context", "prune_every_n_turns", default="50"))

            logger.log_info(f"{Icons.robot} Orac orchestrator initialized with model: {self.model_name}")
            logger.log_info(f"{Icons.settings} Reasoning tags stripped by default: {self.strip_reasoning_tags}")
            logger.log_info(f"{Icons.docs} Protocol version: {PROTOCOL_VERSION}")

        except Exception as e:
            _log_exception("Fatal error during Orac initialization", e)
            raise

    # --- Prompt building ------------------------------------------------------
    def _build_contextual_prompt(self, session_id: str, prompt: str, meta: dict) -> str:
        try:
            prefs = {
                "timezone": (meta or {}).get("timezone", "Europe/London"),
                "force_concise": (meta or {}).get("force_concise"),
            }
            clock = system_clock_line(prefs)

            primer_inline = _orac_system_primer({
                "reply_language": (meta or {}).get("reply_language", self._reply_language)
            })

            raw_fetch = max(4 * max(1, self._history_turn_pairs), 12)
            all_msgs = self.ctx.get_messages_for_prompt(session_id=session_id, limit=raw_fetch)

            if self.enable_prompt_dump:
                # Debug: what we fetched
                try:
                    dbg_lines = [f"{m.get('role', '?').upper():9} | {(m.get('content') or '').strip()}" for m in all_msgs]
                    _dump_debug_blob("history-fetched", "\n".join(dbg_lines))
                except Exception as e:
                    _log_exception("history debug dump failed", e)

            # Drop duplicate of current user prompt if present
            if all_msgs:
                last = all_msgs[-1]
                if (last.get("role") == "user") and ((last.get("content") or "").strip() == (prompt or "").strip()):
                    all_msgs = all_msgs[:-1]

            # Only dialogue moves (user/assistant)
            dialog = [m for m in all_msgs if (m.get("role") in ("user", "assistant"))]

            # Last N turns (pairs) => 2 * turns messages
            need = 2 * max(1, self._history_turn_pairs)
            picked_rev = []
            for m in reversed(dialog):
                picked_rev.append(m)
                if len(picked_rev) >= need:
                    break
            dialog_last_n = list(reversed(picked_rev))

            # Format
            history_lines = []
            for m in dialog_last_n:
                r = (m.get("role") or "").upper()
                c = (m.get("content") or "").strip()
                if not c:
                    continue
                c = c if len(c) <= 1000 else (c[:1000] + " …")
                history_lines.append(f"{r}: {c}")

            lang = (meta or {}).get("reply_language", self._reply_language) or "English"
            final_directive = (
                f"\nFINAL DIRECTIVE: For the CURRENT user message below, respond in {lang} ONLY. "
                "Use 'Recent exchange' as session memory for THIS conversation. "
                "If it contains explicit facts that answer the question (e.g., name, preferences, constraints, "
                "numbers, dates, IDs, URLs), use the most recent consistent fact. "
                "If not present or ambiguous, say you don't know and optionally ask the user to clarify. "
                "Keep the reply concise.\n"
            )

            preamble = (
                    f"{primer_inline}\n"
                    "ROLE: assistant\n"
                    "INSTRUCTIONS: Use the recent context only if relevant.\n\n"
                    f"{clock}\n\n"
                    "Recent exchange (most recent at bottom):\n"
                    + ("\n".join(history_lines) if history_lines else "(no prior context)")
                    + "\n\nUSER (new message):"
            )

            full = f"{preamble}\n{prompt}\n{final_directive}"

            # Inspectable prompt
            short = (full[:1200] + " …") if len(full) > 1200 else full
            logger.log_info(f"{Icons.info} Final prompt (truncated): {short}")
            if self.enable_prompt_dump:
                try:
                    _dump_debug_blob("final-prompt", full)
                except Exception as e:
                    _log_exception("final prompt dump failed", e)

            return full
        except Exception as e:
            _log_exception("Failed to build context preamble (non-fatal)", e)
            return prompt

    def _extract_simple_facts(self, dialog_msgs: list[dict]) -> dict:
        """
        Ultra-light heuristics to lift explicit user-stated facts from recent dialog.
        We bias to the MOST RECENT matching statement.
        Returns a dict like {"name": "Clive", "birthplace": "Hemsworth, West Yorkshire"}.
        """
        facts = {}

        # Walk from newest to oldest; first match wins (i.e., most recent statement)
        for m in reversed(dialog_msgs):
            if (m.get("role") != "user"):
                continue
            text = (m.get("content") or "").strip()
            if not text:
                continue

            # --- name patterns ---
            # e.g., "My name is Clive", "I'm Clive", "I am Clive"
            m_name = re.search(r"\b(?:my name is|i(?:'| a)?m)\s+([A-Z][\w\-']{1,40})\b", text, flags=re.I)
            if m_name and "name" not in facts:
                facts["name"] = m_name.group(1).strip()

            # --- birthplace patterns ---
            # e.g., "I was born in Hemsworth, West Yorkshire"
            m_birth = re.search(r"\bi was born in\s+([^\.!\n]+)", text, flags=re.I)
            if m_birth and "birthplace" not in facts:
                facts["birthplace"] = m_birth.group(1).strip(" .")

            # You can add more lightweight patterns here:
            # - residence: r"\bi live in\s+([^\.!\n]+)"
            # - age: r"\bi am (\d{1,3})\b"
            # - preference: r"\bi (?:prefer|like)\s+([^\.!\n]+)"
            # Keep it conservative to avoid false positives.

        return facts

    def _format_session_facts_block(self, facts: dict) -> str:
        """
        Format facts as a compact, model-friendly block placed near the end of the preamble.
        """
        if not facts:
            return ""
        lines = ["SESSION FACTS (from this conversation):"]
        if "name" in facts:
            lines.append(f"- user_name: {facts['name']}")
        if "birthplace" in facts:
            lines.append(f"- user_birthplace: {facts['birthplace']}")
        # append any future fields in a stable order if added
        return "\n".join(lines) + "\n"

    # --- Model availability checks -------------------------------------------
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

    # --- Output hygiene -------------------------------------------------------
    def _strip_reasoning_tags(self, text: str) -> str:
        """
        Strips <think>...</think> blocks. If we detect a dangling <think>
        with no closing </think>, treat it as incomplete and drop it entirely.
        """
        if not isinstance(text, str):
            return ""
        if "<think>" in text and "</think>" not in text:
            return ""
        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    # --- Session / policy helpers --------------------------------------------
    def _derive_session_id(self, meta: dict, auth_user: str) -> str:
        """
        Build a stable session id from auth user + client.
        Normalize case/whitespace so 'Slave' vs 'slave' or ' clive ' don't fork conversations.
        Prefer an explicit meta.session_id if provided and non-empty.
        """
        sid = (meta or {}).get("session_id")
        if isinstance(sid, str) and sid.strip():
            return sid.strip()

        try:
            u = (auth_user or "unknown").strip().lower()
        except Exception:
            u = str(auth_user).strip().lower()

        try:
            c = ((meta or {}).get("client", "unknown") or "unknown").strip().lower()
        except Exception:
            c = str((meta or {}).get("client", "unknown")).strip().lower()

        return f"{u}::{c}"

    def _maybe_prune(self, session_id: str, last_turn_index: int) -> None:
        try:
            n = max(0, int(self._prune_after_turns))
            if n and last_turn_index and (last_turn_index % n) == 0:
                deleted = self.ctx.prune_context(
                    session_id=session_id,
                    keep_messages=self._keep_messages,
                    archive_conversation=False,
                )
                if deleted:
                    logger.log_info(f"{Icons.broom} Pruned {deleted} messages for {session_id} at turn {last_turn_index}")
        except Exception as e:
            _log_exception("Context prune failed (non-fatal)", e)

    # --- Response builder -----------------------------------------------------
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
                    "total_tokens": int(prompt_tokens) + int(completion_tokens),
                },
            },
            "error": None,
        }
        try:
            validate_frame(resp)
        except Exception as e:
            _log_exception("Response failed protocol validation (returning anyway)", e)
        return resp

    # --- Auto-title helpers ---------------------------------------------------
    def _sanitize_title(self, text: str) -> str:
        """
        Enforce short, tidy, English title: <= 6 words, Title Case, no quotes/punctuation.
        """
        if not isinstance(text, str):
            return ""
        t = text.strip()
        t = t.strip('"\''"“”‘’` ")
        t = re.sub(r"\s+", " ", t)
        t = re.sub(r"[^\w\s-]", "", t)
        t = " ".join(t.split()[:6]).title()
        return t[:120].strip()

    def _maybe_set_conversation_title(self, session_id: str, meta: dict) -> None:
        """
        If the conversation has at least 2 turns and no title yet, ask the LLM for a short title and store it.
        """
        try:
            # Gracefully handle older ContextManager versions without the getter
            existing = None
            try:
                existing = self.ctx.get_conversation_title(session_id)
            except AttributeError:
                pass
            if existing:
                return

            if self.ctx.last_turn_index(session_id) < 2:
                return

            msgs = self.ctx.get_messages_for_prompt(session_id=session_id, limit=12)
            dialog = [m for m in msgs if m.get("role") in ("user", "assistant")]

            lines = ["Dialog:"]
            for m in dialog[-8:]:
                role = (m.get("role") or "").upper()
                content = (m.get("content") or "").replace("\n", " ").strip()
                lines.append(f"{role}: {content}")
            lines += [
                "",
                "Instruction: Propose a very short English conversation title (<= 6 words).",
                "Do not include quotes, punctuation, emojis, or vendor/model names.",
                "Return ONLY the title text.",
            ]
            title_prompt = "\n".join(lines)

            raw = self.llm.send_prompt(prompt_type="U", prompt=title_prompt, stream=False)
            if hasattr(raw, "content"):
                raw = raw.content
            if not isinstance(raw, str):
                raw = str(raw)

            candidate = self._sanitize_title(raw)
            if not candidate:
                last_user = next((m for m in reversed(dialog) if m.get("role") == "user"), None)
                candidate = self._sanitize_title((last_user or {}).get("content", "") or "Conversation")

            if candidate:
                self.ctx.set_conversation_title(session_id, candidate)
                logger.log_info(f"{Icons.tick} Conversation titled: {candidate}")

        except Exception as e:
            _log_exception("Auto-title failed (non-fatal)", e)

    # --- Main request handler -------------------------------------------------
    async def handle_request(self, message: str) -> str:
        try:
            req_env = json.loads(message)  # strict JSON
        except Exception as e:
            _log_exception("Failed to parse request JSON", e)
            err_env = {
                "v": 1, "type": "response", "id": new_id("res"),
                "reply_to": None, "ts": iso_now(), "route": "orac.prompt",
                "meta": {"status": "error", "model": self.model_name},
                "payload": None, "error": {"code": "BAD_JSON", "message": str(e)},
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
                    "error": {"code": "UNAUTHORISED", "message": auth_res.reason or "unauthorised"},
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
                    "error": {"code": "INVALID_FRAME", "message": str(e)},
                }
                return json.dumps(err, ensure_ascii=False)

            if req_env.get("route") != "orac.prompt":
                raise ValueError("Unsupported request type/route")

            # --- Extract prompt & meta -----------------------------------------
            messages = (req_env.get("payload") or {}).get("messages") or []
            prompt = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "").strip()
            meta = req_env.get("meta") or {}
            show_reasoning = bool(meta.get("show_reasoning", not self.strip_reasoning_tags))
            client = meta.get("client", "unknown")
            auth_user = getattr(auth_res, "user", "unknown")

            logger.log_info(f"{Icons.info} [{client}] user={auth_user} Prompt received")
            logger.log_debug(f"Prompt text: {prompt}")
            logger.log_info(f"meta.show_reasoning={show_reasoning} (strip_reasoning_default={self.strip_reasoning_tags})")

            # --- Session + conversation ----------------------------------------
            session_id = self._derive_session_id(meta, auth_user)
            try:
                self.ctx.ensure_conversation(user_name=auth_user, session_id=session_id, llm_id=None)
            except Exception as e:
                _log_exception("ensure_conversation failed (non-fatal)", e)

            # --- Ensure a system primer is stored once per conversation ---------
            try:
                if self.ctx.last_turn_index(session_id) == 0:
                    primer = _orac_system_primer({"reply_language": self._reply_language})
                    self.ctx.save_system_turn(session_id, auth_user, primer, meta={
                        "kind": "primer",
                        "ts": iso_now(),
                        "protocol_version": PROTOCOL_VERSION,
                    })
            except Exception as e:
                _log_exception("Failed to persist system primer (non-fatal)", e)

            # --- Save USER turn -------------------------------------------------
            user_meta = {
                "client": client,
                "protocol_version": PROTOCOL_VERSION,
                "ts": iso_now(),
                "req_id": req_env.get("id"),
            }
            try:
                save_res_u = self.ctx.save_user_turn(session_id, auth_user, prompt, meta=user_meta)
                logger.log_debug(f"Saved user msg: {save_res_u}")
            except Exception as e:
                _log_exception("Failed to persist user turn (non-fatal)", e)

            # --- Build context-primed prompt -----------------------------------
            final_prompt = self._build_contextual_prompt(session_id, prompt, meta)
            short = (final_prompt[:1200] + " …") if len(final_prompt) > 1200 else final_prompt
            logger.log_info(f"{Icons.info} Final prompt (truncated): {short}")
            if self.enable_prompt_dump:
                _dump_debug_blob("final-prompt", final_prompt)

            # === Call backend (non-streaming path) ===
            try:
                raw = self.llm.send_prompt(prompt_type="U", prompt=final_prompt, stream=False)
            except Exception as e:
                _log_exception("LLM backend call failed", e)
                err = {
                    "v": 1, "type": "response", "id": new_id("res"),
                    "reply_to": req_env.get("id"), "ts": iso_now(), "route": "orac.prompt",
                    "meta": {"status": "error", "model": self.model_name, "req_id": req_env.get("id")},
                    "payload": None,
                    "error": {"code": "LLM_BACKEND_ERROR", "message": str(e)},
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
                content = stripped if stripped else raw

            # Final guard: never send empty content
            if not content:
                logger.log_warning("Backend returned empty content after stripping; using friendly fallback.")
                content = "Hello! 👋"

            # --- Save ASSISTANT turn -------------------------------------------
            asst_meta = {
                "client": client,
                "protocol_version": PROTOCOL_VERSION,
                "ts": iso_now(),
                "req_id": req_env.get("id"),
                "show_reasoning": show_reasoning,
            }
            last_ti = 0
            try:
                save_res_a = self.ctx.save_assistant_turn(session_id, auth_user, content, meta=asst_meta)
                last_ti = int(save_res_a.get("turn_index", 0))
                logger.log_debug(f"Saved assistant msg: {save_res_a}")
            except Exception as e:
                _log_exception("Failed to persist assistant turn (non-fatal)", e)

            # Try to set a short conversation title once there is enough context
            self._maybe_set_conversation_title(session_id, meta)

            # --- Periodic prune (based on assistant turn index) ----------------
            self._maybe_prune(session_id, last_ti)

            # --- Build response frame ------------------------------------------
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
                "payload": None, "error": {"code": "SERVER_ERROR", "message": str(e)},
            }
            return json.dumps(err_env, ensure_ascii=False)


# --- Module-level main() runner ----------------------------------------------
async def main():
    try:
        orchestrator = Orac()
        listener = OracListener(orchestrator=orchestrator, host="127.0.0.1", port=8765)
        await listener.start_server()
    except Exception as e:
        _log_exception("Fatal in main()", e)
        raise


# --- Entrypoint ---------------------------------------------------------------
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
