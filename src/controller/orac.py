"""Oracle orchestrator, orac.py (protocol-enabled, non-streaming response)"""

# Author: Clive Bostock
# Date: 2026-04-29
# Description: Orac runtime orchestration, including conversation-aware LLM
#   selection and fallback handling.

import asyncio
import subprocess
import re
import json
import threading
import uuid
import os
import time
import sys
import traceback
from decimal import Decimal
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo
import yaml

from model.network import OracListener
from model.llm_connector import LMStudioConnector, OllamaConnector
from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from lib.icons import Icons
from lib.logutil import Logger
from model.orac_auth import FrameAuthChain, ZenFrameAuth
from model.context_manager import OracContextManager
from model.plugin_routing import (
    HashEmbeddingProvider,
    PluginManager,
    PluginRoutingHandoff,
    render_plugin_routing_hints,
)
from model.plugin_router import PluginRouter
from lib.session_manager import DBSession
from lib.user_security import UserSecurity

# --- Paths / Config -----------------------------------------------------------
LOG_DIR = project_home() / "logs"
APP_HOME = project_home()
RESOURCES_DIR = APP_HOME / "resources"
CONFIG_DIR = RESOURCES_DIR / "config"
CONFIG_FILE_PATH = CONFIG_DIR / "orac.ini"
SYSTEM_PROMPT_POLICY_FILE_PATH = CONFIG_DIR / "orac_system_prompt.yaml"
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


def _bool_env_flag(value: str | None) -> bool:
    """Interpret an environment flag value as boolean."""
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "t", "y", "yes", "on"}

# --- Small utils --------------------------------------------------------------
def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _json_default(value: Any) -> Any:
    """Serialize Oracle-native numeric values into JSON-compatible scalars."""
    if isinstance(value, Decimal):
        normalized = value.normalize()
        if normalized == normalized.to_integral():
            return int(normalized)
        return float(normalized)
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def _close_db_session_quietly(db_session: DBSession | None) -> None:
    """Close a DB session without surfacing shutdown noise."""
    if db_session is None:
        return

    try:
        db_session.close()
    except Exception:
        pass
    finally:
        try:
            db_session.connection_succeeded = False
        except Exception:
            pass


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def new_session_id(base: str) -> str:
    """Return a fresh session id suffix for explicit conversation rollover."""
    return f"{base}#{int(time.time() * 1000)}"


def _log_exception(prefix: str, exc: BaseException):
    """Log an exception with full stack trace."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.log_error(f"{prefix}: {exc}\n{tb}")


def _timezone_location_label(tz_name: str) -> str:
    """Return a human-readable fallback location label from an IANA timezone."""
    parts = [part for part in str(tz_name or "").split("/") if part]
    if not parts:
        return "UTC"
    return parts[-1].replace("_", " ")


def system_clock_line(prefs: dict) -> str:
    """Render time and location context for the current session."""
    tz_name = (prefs or {}).get("timezone", "Europe/London")
    weather_location = str((prefs or {}).get("weather_location") or "").strip()
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
        f"Current UTC time: {utc_iso}.",
        f"Session timezone preference: {tz_name}.",
        f"Time in that timezone: {local_str}; day: {dow}.",
    ]
    if weather_location:
        lines.append(f"Assume your current location is {weather_location}.")
    else:
        lines.append(
            f"No explicit weather location is set. Assume your current location is "
            f"{_timezone_location_label(tz_name)} based on the session timezone."
        )
    if "date_format" in (prefs or {}):
        lines.append(f"Use date format {prefs['date_format']}.")
    if (prefs or {}).get("force_concise") is True:
        lines.append("Keep answers concise.")
    return "\n".join(lines)


def _load_system_prompt_policy(policy_path: Path) -> dict[str, Any]:
    """Load the Orac system prompt policy from YAML."""
    with policy_path.open("r", encoding="utf-8") as policy_file:
        loaded = yaml.safe_load(policy_file) or {}

    if not isinstance(loaded, dict):
        raise ValueError(
            f"System prompt policy at {policy_path} must contain a YAML mapping."
        )

    title = loaded.get("title")
    if not isinstance(title, str) or not title.strip():
        raise ValueError(
            f"System prompt policy at {policy_path} is missing a valid 'title'."
        )

    return loaded


def _render_policy_lines(lines: list[str]) -> str:
    """Render a list of policy lines as bullet points."""
    return "\n".join(f"- {line}" for line in lines if isinstance(line, str) and line.strip())


def _split_prompt_text(text: Any) -> list[str]:
    """Split stored prompt text into clean instruction lines."""
    if not isinstance(text, str):
        return []

    cleaned: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        line = re.sub(r"^[\-\*\u2022]\s*", "", line)
        cleaned.append(line)
    return cleaned


def _as_bool(value: Any) -> bool | None:
    """Normalise database and JSON boolean-like values."""
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        norm = value.strip().lower()
        if norm in {"true", "t", "1", "y", "yes"}:
            return True
        if norm in {"false", "f", "0", "n", "no"}:
            return False
    return None


def _as_int(value: Any, default: int) -> int:
    """Return an integer value with fallback."""
    try:
        return int(value)
    except Exception:
        return default


def _personality_rule_lines(personality: dict[str, Any]) -> list[str]:
    """Render structured personality settings into prompt rules."""
    if not personality:
        return []

    code = str(personality.get("PERSONALITY_CODE") or "").strip().upper()
    name = str(personality.get("PERSONALITY_NAME") or code or "Orac").strip()
    lines = [f"Selected personality: {name} ({code})."]

    attitude_level = _as_int(personality.get("ATTITUDE_BASE_LEVEL"), 1)
    attitude_map = {
        0: "Maintain a neutral, composed tone.",
        1: "Maintain a dry, self-possessed tone.",
        2: "Maintain a sharper tone when appropriate, while remaining useful.",
    }
    lines.append(attitude_map.get(attitude_level, attitude_map[1]))

    sarcasm_level = _as_int(personality.get("SARCASM_LEVEL"), 1)
    sarcasm_map = {
        0: "Do not use sarcasm.",
        1: "Light sarcasm is acceptable when it sharpens clarity.",
        2: "A noticeable sarcastic edge is acceptable, but do not become hostile.",
    }
    lines.append(sarcasm_map.get(sarcasm_level, sarcasm_map[1]))

    verbosity_level = _as_int(personality.get("VERBOSITY_LEVEL"), 1)
    verbosity_map = {
        0: "Prefer concise answers by default.",
        1: "Prefer balanced detail.",
        2: "Prefer fuller explanations when useful.",
    }
    lines.append(verbosity_map.get(verbosity_level, verbosity_map[1]))

    humour = _as_bool(personality.get("ALLOW_HUMOUR"))
    if humour is True:
        lines.append("Humour is allowed when appropriate.")
    elif humour is False:
        lines.append("Do not use humour.")

    critique = _as_bool(personality.get("ALLOW_CRITIQUE"))
    if critique is True:
        lines.append("Challenge weak assumptions when necessary.")
    elif critique is False:
        lines.append("Avoid confrontational critique; correct gently.")

    precision = _as_bool(personality.get("ENFORCE_PRECISION"))
    if precision is True:
        lines.append("Prioritise precision and careful wording.")

    uncertainty = _as_bool(personality.get("ADMIT_UNCERTAINTY"))
    if uncertainty is True:
        lines.append("State uncertainty plainly when confidence is limited.")
    elif uncertainty is False:
        lines.append("Do not hedge unnecessarily; speak decisively when the facts support it.")

    lines.extend(_split_prompt_text(personality.get("SYSTEM_PROMPT")))
    lines.extend(_split_prompt_text(personality.get("STYLE_PROMPT")))
    return lines


def _normalise_discovered_model_names(models: list[Any]) -> list[str]:
    """Return a stable, de-duplicated list of discovered model names."""
    seen: set[str] = set()
    result: list[str] = []

    for item in models:
        name = str(item or "").strip()
        if not name:
            continue
        if name in seen:
            continue
        seen.add(name)
        result.append(name)

    return result


# --- System primer (module-level, used both inline and for first system turn) -
def _orac_system_primer(meta: dict, policy: dict[str, Any]) -> str:
    """
    Single source of truth for Orac's persona, language policy, and safety rails.
    """
    lang_pref = (meta or {}).get("reply_language", "English")
    lines: list[str] = []

    identity = policy.get("identity", {})
    assistant_name = identity.get("assistant_name", "Orac")
    vendor_claims = identity.get("disallowed_vendor_claims", [])
    if vendor_claims:
        claims_text = ", ".join(vendor_claims[:-1])
        if len(vendor_claims) > 1:
            claims_text = f"{claims_text}, or {vendor_claims[-1]}"
        else:
            claims_text = vendor_claims[0]
        lines.append(
            f"Your name is {assistant_name}. Never claim to be {claims_text}."
        )

    for section_name in (
        "response_style",
        "language",
        "memory",
        "profile_facts",
        "safety",
    ):
        section = policy.get(section_name, {})
        section_lines = section.get("rules", [])
        if section_name == "language":
            section_lines = [
                line.format(reply_language=lang_pref)
                for line in section_lines
            ]
        lines.extend(section_lines)

    rendered = f"{policy['title']}\n{_render_policy_lines(lines)}\n"
    personality_lines = _personality_rule_lines(
        (meta or {}).get("orac_personality") or {}
    )
    if personality_lines:
        rendered += (
            "\nPersonality overlay:\n"
            f"{_render_policy_lines(personality_lines)}\n"
        )
    return rendered



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
            self._orac_run_dir = Path(os.environ.get("ORAC_RUN_DIR", "/run/orac"))
            self._dump_context_flag = self._orac_run_dir / "dump-context.once"
            self._force_prompt_dump = _bool_env_flag(os.environ.get("ORAC_FORCE_PROMPT_DUMP"))
            self.strip_reasoning_tags = (
                self.config_mgr.config_value("settings", "strip_reasoning_tags", default="true").lower() == "true"
            )
            policy_path_raw = self.config_mgr.config_value(
                "context",
                "system_prompt_policy_file",
                default=str(SYSTEM_PROMPT_POLICY_FILE_PATH),
            )
            policy_path = Path(policy_path_raw)
            if not policy_path.is_absolute():
                policy_path = APP_HOME / policy_path
            self._system_prompt_policy_path = policy_path
            self._system_prompt_policy = _load_system_prompt_policy(policy_path)
            self._history_turn_pairs = int(
                self.config_mgr.config_value("context", "history_turn_pairs", default="6")
            )
            self._reply_language = self.config_mgr.config_value("context", "reply_language", default="English")
            self._persistence_failures: list[dict[str, str]] = []
            self._fail_on_persistence_error = False

            conv_timeout_minutes = int(
                self.config_mgr.config_value("context", "conversation_timeout", default="60")
            )
            self._use_history = self.config_mgr.bool_config_value(section='context', key='enable_context_history', default=True)

            if not self._use_history:
                logger.log_warning(
                    f"{Icons.warn} context augmentation DISABLED "
                    "(history still being recorded for later use)"
                )
            else:
                logger.log_info(f"{Icons.tick} context augmentation ENABLED")

            self._conversation_timeout_secs = max(0, conv_timeout_minutes * 60)
            logger.log_info(
                f"[context] conversation_timeout={conv_timeout_minutes} minute(s) -> {self._conversation_timeout_secs}s")

            # inside Orac.__init__ (after reading other context settings)
            self._economy_mode = (
                        self.config_mgr.config_value('context', 'economy', default='normal') or 'normal').lower()

            # Auto-transition policy on timeout rollover
            self._archive_on_rollover = self.config_mgr.bool_config_value("context", "archive_on_rollover", default=False)

            self._close_on_rollover = self.config_mgr.bool_config_value("context", "close_on_rollover", default=True)

            # Accept meta.session_id from caller? (default: no)
            self._allow_external_session_id = self.config_mgr.bool_config_value(
                "context", "allow_external_session_id", default=False
            )

            # --- in Orac.__init__ after other context settings ---
            # How to scope session ids: 'user' (stable) or 'user+client' (split by client)
            self._session_scope = (
                self.config_mgr.config_value("context", "session_scope", default="user").strip().lower()
            )
            # Treat the client id as stable or normalize away ephemeral bits (ports/PIDs/UUIDs)
            self._normalize_client = self.config_mgr.bool_config_value("context", "normalize_client",
                                                                       default=True)


            # Per-mode history budgets in *approximate tokens* (very conservative).
            # You can override any of these in orac.ini via context.history_budget_tokens.
            default_budget_by_mode = {
                'thrifty': 600,  # ~2–3 short turns
                'normal': 1200,  # good default
                'lavish': 2400,  # longer chats
            }
            cfg_budget = self.config_mgr.config_value('context', 'history_budget_tokens', default='')
            try:
                self._history_budget_tokens = int(cfg_budget) if str(
                    cfg_budget).strip() else default_budget_by_mode.get(self._economy_mode, 1200)
            except Exception:
                self._history_budget_tokens = default_budget_by_mode.get(self._economy_mode, 1200)

            # Reserve some headroom for the current user message and our preamble
            self._history_budget_reserve = int(
                self.config_mgr.config_value('context', 'history_budget_reserve', default='300'))

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
            self._llm_connector_cache: dict[tuple[str, str, str], Any] = {
                (self.llm_service_id.strip().lower(), self.service_url.strip(), self.model_name.strip()): self.llm,
            }
            self._available_backend_models: set[str] = {self.model_name.strip()}
            self._available_backend_model_details: dict[str, dict[str, Any]] = {}

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
            self.ctx = OracContextManager(self.db_session, logger=logger)
            self._sync_llm_registry()
            self._llm_probe_stop = threading.Event()
            self._llm_probe_thread: threading.Thread | None = None
            self._llm_probe_interval_secs = int(
                self.config_mgr.config_value(
                    "context",
                    "llm_probe_interval_secs",
                    default="30",
                )
            )
            self._start_llm_probe_worker()
            self._keep_messages = int(self.config_mgr.config_value("context", "keep_messages", default="200"))
            self._prune_after_turns = int(self.config_mgr.config_value("context", "prune_every_n_turns", default="50"))
            self._plugin_routing_enabled = self.config_mgr.bool_config_value(
                "plugin_routing", "enabled", default=True
            )
            self._plugin_routing_bootstrap_on_startup = self.config_mgr.bool_config_value(
                "plugin_routing", "bootstrap_on_startup", default=True
            )
            self._plugin_routing_candidate_count = self.config_mgr.int_config_value(
                "plugin_routing", "candidate_count", default=3
            )
            min_score_raw = self.config_mgr.config_value(
                "plugin_routing", "min_score", default=""
            ).strip()
            self._plugin_routing_min_score = float(min_score_raw) if min_score_raw else None
            self.plugin_manager: PluginManager | None = None
            self.plugin_router: PluginRouter | None = None
            self._plugin_routing_ready = False
            self._init_plugin_routing()

            logger.log_info(f"{Icons.robot} Orac orchestrator initialized with model: {self.model_name}")
            logger.log_info(f"{Icons.settings} Reasoning tags stripped by default: {self.strip_reasoning_tags}")
            logger.log_info(f"{Icons.docs} Protocol version: {PROTOCOL_VERSION}")

        except Exception as e:
            _log_exception("Fatal error during Orac initialization", e)
            raise

    def _consume_prompt_dump_request(self) -> bool:
        """Return True when a one-shot context dump has been requested."""
        if self._force_prompt_dump:
            return True

        try:
            if self._dump_context_flag.exists():
                self._dump_context_flag.unlink(missing_ok=True)
                logger.log_info(
                    f"{Icons.info} Consumed one-shot context dump request from {self._dump_context_flag}"
                )
                return True
        except Exception as e:
            _log_exception("Failed to consume one-shot context dump request", e)

        return False

    def _should_dump_prompt(self) -> bool:
        """Return True when the current request should emit prompt debug dumps."""
        if self.enable_prompt_dump:
            return True
        return self._consume_prompt_dump_request()

    # --- Prompt building ------------------------------------------------------
    def _build_contextual_prompt(
        self,
        session_id: str,
        prompt: str,
        meta: dict,
        auth_user: str,
        plugin_routing_handoff: PluginRoutingHandoff | None = None,
    ) -> str:
        try:
            dump_prompt = self._should_dump_prompt()
            prefs = {
                "timezone": meta.get("timezone", "Europe/London"),
                "weather_location": meta.get("weather_location"),
                "force_concise": meta.get("force_concise"),
            }
            clock = system_clock_line(prefs)
            routing_block = render_plugin_routing_hints(plugin_routing_handoff)
            user_facts_block = ""
            try:
                user_profile = self.ctx.get_user_profile(auth_user)
            except Exception as e:
                _log_exception("Failed to load authenticated user profile", e)
                user_profile = {}
            if user_profile:
                fact_lines = ["Known user facts:"]
                if user_profile.get("authenticated_username"):
                    fact_lines.append(
                        f"- Authenticated username: {user_profile['authenticated_username']}"
                    )
                if user_profile.get("display_name"):
                    fact_lines.append(
                        f"- Display name: {user_profile['display_name']}"
                    )
                user_facts_block = "\n".join(fact_lines) + "\n\n"

            primer_meta = {
                "reply_language": meta.get("reply_language", self._reply_language),
                "orac_personality": meta.get("orac_personality"),
            }
            primer_inline = _orac_system_primer(
                primer_meta,
                self._system_prompt_policy,
            )

            # === NEW: short-circuit if history use is disabled ===
            if not getattr(self, "_use_history", True):
                lang = meta.get("reply_language", self._reply_language) or "English"
                final_directive = (
                    f"\nFINAL DIRECTIVE: For the CURRENT user message below, respond in {lang} ONLY. "
                    "Ignore any prior conversation for this reply. Keep the reply concise.\n"
                )
                preamble = (
                    f"{primer_inline}\n"
                    "ROLE: assistant\n"
                    "INSTRUCTIONS: Prior conversation is DISABLED for this reply; use ONLY the new user message.\n\n"
                    f"{clock}\n\n"
                    f"{user_facts_block}"
                    f"{routing_block}"
                    "Recent exchange: (context disabled)\n\n"
                    "USER (new message):"
                )
                full = f"{preamble}\n{prompt}\n{final_directive}"
                if dump_prompt:
                    try:
                        short = (full[:2000] + " …") if len(full) > 2000 else full
                        logger.log_info(f"{Icons.info} Final prompt (truncated): {short}")
                        _dump_debug_blob("final-prompt", full)
                    except Exception as e:
                        _log_exception("final prompt dump failed", e)
                return full

            # --- existing history-enabled path (unchanged) ---
            raw_fetch = max(20, min(200, (self._history_budget_tokens // 50) * 4))
            all_msgs = self.ctx.get_messages_for_prompt(session_id=session_id, limit=raw_fetch)

            if dump_prompt:
                try:
                    dbg_lines = []
                    for m in all_msgs:
                        dbg_lines.append(f"{(m.get('role') or '?').upper():9} | {(m.get('content') or '').strip()}")
                    _dump_debug_blob("history-fetched", "\n".join(dbg_lines))
                except Exception as e:
                    _log_exception("history debug dump failed", e)

            if all_msgs:
                last = all_msgs[-1]
                if (last.get("role") == "user") and ((last.get("content") or "").strip() == (prompt or "").strip()):
                    all_msgs = all_msgs[:-1]

            prompt_cost = self._estimate_tokens(prompt)
            reserve = max(0, self._history_budget_reserve + prompt_cost)
            budget_for_history = max(0, self._history_budget_tokens - reserve)

            dialog_last_n = self._select_dialog_under_budget(all_msgs, budget_tokens=budget_for_history)

            history_lines = []
            for m in dialog_last_n:
                r = (m.get("role") or "").upper()
                c = (m.get("content") or "").strip()
                if c:
                    history_lines.append(f"{r}: {c}")

            lang = meta.get("reply_language", self._reply_language) or "English"
            final_directive = (
                f"\nFINAL DIRECTIVE: For the CURRENT user message below, respond in {lang} ONLY. "
                "Use 'Recent exchange' to resolve references, follow-up wording, and user-provided session facts. "
                "For ordinary factual questions, use your general knowledge as well as relevant context. "
                "Do not treat earlier assistant answers as authoritative if they conflict with reliable knowledge; "
                "correct materially wrong earlier answers plainly. "
                "If a proper noun appears misspelled or variant, state the likely interpretation and answer under "
                "that interpretation; ask for clarification only when multiple plausible meanings remain. "
                "For personal/session facts, only claim facts present in authenticated context or recent exchange. "
                "Keep the reply concise.\n"
            )

            preamble = (
                    f"{primer_inline}\n"
                    "ROLE: assistant\n"
                    "INSTRUCTIONS: Use the recent context only if relevant.\n\n"
                    f"{clock}\n\n"
                    f"{user_facts_block}"
                    f"{routing_block}"
                    "Recent exchange (most recent at bottom):\n"
                    + ("\n".join(history_lines) if history_lines else "(no prior context)")
                    + "\n\nUSER (new message):"
            )

            full = f"{preamble}\n{prompt}\n{final_directive}"

            if dump_prompt:
                try:
                    short = (full[:2000] + " …") if len(full) > 2000 else full
                    logger.log_info(f"{Icons.info} Final prompt (truncated): {short}")
                    _dump_debug_blob("final-prompt", full)
                except Exception as e:
                    _log_exception("final prompt dump failed", e)

            return full

        except Exception as e:
            _log_exception("Failed to build context preamble (non-fatal)", e)
            return prompt

    def _sync_llm_registry(self) -> None:
        """Discover models from the active backend and upsert them into the registry."""
        try:
            discovered = _normalise_discovered_model_names(self.llm.list_models())
        except Exception as e:
            _log_exception(
                "LLM model discovery failed (registry sync skipped)",
                e,
            )
            return

        self._refresh_backend_model_inventory()

        if not discovered:
            self._available_backend_models = {self.model_name.strip()}
            logger.log_warning(
                "LLM model discovery returned no models; registry sync skipped."
            )
            return

        self._available_backend_models = set(discovered)

        provider = self.llm_service_id.strip().lower()
        synced = 0
        inserted = 0
        updated = 0

        try:
            existing_rows = self.db_session.dict_sql_dataset(
                """
                select llm_id,
                       name,
                       provider,
                       model,
                       context_policy,
                       max_context_tokens,
                       is_enabled,
                       properties
                  from orac_api.llm_registry_v
                """
            )
            existing_by_key = {
                (
                    str(row.get("PROVIDER") or "").strip().lower(),
                    str(row.get("MODEL") or "").strip(),
                ): row
                for row in existing_rows
            }

            with self.db_session.cursor() as cursor:
                for model_name in discovered:
                    key = (provider, model_name)
                    existing = existing_by_key.get(key)
                    existing_properties = (
                        existing.get("PROPERTIES")
                        if existing
                        else None
                    )
                    model_metadata = self._lookup_backend_model_metadata(model_name)
                    existing_context_policy = (
                        str(existing.get("CONTEXT_POLICY") or "").strip()
                        if existing
                        else ""
                    )
                    context_policy = existing_context_policy or "unresolved"
                    properties = self._build_llm_registry_properties(
                        existing_properties,
                        provider=provider,
                        service_url=self.service_url,
                        model_name=model_name,
                        is_default_runtime_model=(
                            model_name == self.model_name
                        ),
                        model_metadata=model_metadata,
                    )

                    if existing:
                        cursor.execute(
                            """
                            update orac_api.llm_registry_v
                               set provider = :provider,
                                   model = :model,
                                   context_policy = :context_policy,
                                   properties = json(:properties)
                             where llm_id = :llm_id
                            """,
                            {
                                "provider": provider,
                                "model": model_name,
                                "context_policy": context_policy,
                                "properties": properties,
                                "llm_id": existing["LLM_ID"],
                            },
                        )
                        updated += 1
                    else:
                        cursor.execute(
                            """
                            insert into orac_api.llm_registry_v
                              (name, provider, model, context_policy,
                               max_context_tokens, is_enabled, properties)
                            values
                              (:name, :provider, :model, :context_policy,
                               null, 'Y', json(:properties))
                            """,
                            {
                                "name": model_name,
                                "provider": provider,
                                "model": model_name,
                                "context_policy": context_policy,
                                "properties": properties,
                            },
                        )
                        inserted += 1

                    synced += 1

                self.db_session.commit()
        except Exception as e:
            _log_exception("LLM registry sync failed", e)
            try:
                self.db_session.rollback()
            except Exception:
                logger.log_debug(
                    "Ignored rollback failure after llm registry sync error."
                )
            return

        logger.log_info(
            f"{Icons.tick} LLM registry sync complete: "
            f"discovered={len(discovered)} synced={synced} "
            f"inserted={inserted} updated={updated}"
        )

    @staticmethod
    def _build_llm_registry_properties(
        existing_properties: Any,
        *,
        provider: str,
        service_url: str,
        model_name: str,
        is_default_runtime_model: bool,
        model_metadata: dict[str, Any] | None = None,
    ) -> str:
        """Merge startup sync metadata into existing registry properties.

        Args:
            existing_properties (Any): Existing JSON properties payload.
            provider (str): LLM provider name.
            service_url (str): Backend service URL.
            model_name (str): Model name being synchronised.
            is_default_runtime_model (bool): Whether this is the configured model.

        Returns:
            str: JSON document suitable for persistence in the registry.
        """
        merged: dict[str, Any] = {}

        if isinstance(existing_properties, dict):
            merged.update(existing_properties)
        elif isinstance(existing_properties, str) and existing_properties.strip():
            try:
                parsed = json.loads(existing_properties)
            except Exception:
                parsed = {}
            if isinstance(parsed, dict):
                merged.update(parsed)

        merged.update(
            {
                "discovered_by": "startup_sync",
                "service_url": service_url,
                "provider": provider,
                "model": model_name,
                "is_default_runtime_model": is_default_runtime_model,
            }
        )
        if model_metadata:
            merged.update(model_metadata)
        return json.dumps(merged, ensure_ascii=False, default=_json_default)

    def _refresh_backend_model_inventory(self) -> dict[str, dict[str, Any]]:
        """Refresh cached backend model metadata used for registry updates."""
        inventory: dict[str, dict[str, Any]] = {}
        details_getter = getattr(self.llm, "list_model_details", None)
        if not callable(details_getter):
            self._available_backend_model_details = inventory
            return inventory

        try:
            discovered_details = details_getter()
        except Exception as e:
            _log_exception("Backend model metadata discovery failed", e)
            self._available_backend_model_details = inventory
            return inventory

        for item in discovered_details or []:
            model_metadata = self._normalise_backend_model_details(item)
            model_name = str(model_metadata.get("name") or "").strip()
            if not model_name:
                continue
            inventory[model_name] = model_metadata
            inventory[model_name.lower()] = model_metadata

        self._available_backend_model_details = inventory
        return inventory

    def _lookup_backend_model_metadata(self, model_name: str) -> dict[str, Any]:
        """Look up cached backend metadata for a discovered model name."""
        normalized = (model_name or "").strip()
        if not normalized:
            return {}

        backend_model_details = getattr(self, "_available_backend_model_details", {})
        if not backend_model_details:
            self._refresh_backend_model_inventory()
            backend_model_details = getattr(self, "_available_backend_model_details", {})

        return backend_model_details.get(normalized) or backend_model_details.get(normalized.lower()) or {}

    @staticmethod
    def _normalise_backend_model_details(model_details: Any) -> dict[str, Any]:
        """Convert backend model metadata into a JSON-safe mapping."""
        if isinstance(model_details, str):
            name = model_details.strip()
            return {"name": name} if name else {}

        if not isinstance(model_details, dict):
            return {}

        name = str(model_details.get("name") or model_details.get("id") or "").strip()
        if not name:
            return {}

        normalized: dict[str, Any] = {"name": name}
        details = model_details.get("details")
        details_map = details if isinstance(details, dict) else {}

        size_bytes = model_details.get("size_bytes", model_details.get("size"))
        if size_bytes in (None, ""):
            size_bytes = details_map.get("size_bytes")
        if size_bytes not in (None, ""):
            try:
                normalized_size_bytes = int(size_bytes)
                if normalized_size_bytes >= 0:
                    normalized["size_bytes"] = normalized_size_bytes
                    normalized["size_mb"] = int(round(normalized_size_bytes / (1024 * 1024)))
            except Exception:
                pass

        size_mb = model_details.get("size_mb")
        if size_mb in (None, ""):
            size_mb = details_map.get("size_mb")
        if size_mb not in (None, ""):
            try:
                normalized["size_mb"] = int(round(float(size_mb)))
            except Exception:
                pass

        parameter_size = model_details.get("parameter_size") or details_map.get("parameter_size")
        if parameter_size not in (None, ""):
            normalized["parameter_size"] = str(parameter_size)

        quantization_level = model_details.get("quantization_level") or details_map.get("quantization_level")
        if quantization_level not in (None, ""):
            normalized["quantization_level"] = str(quantization_level)

        return normalized

    def _start_llm_probe_worker(self) -> None:
        """Start a background worker that probes unresolved LLM rows."""
        if self._llm_probe_thread and self._llm_probe_thread.is_alive():
            return

        thread = threading.Thread(
            target=self._llm_probe_worker_loop,
            name="orac-llm-probe",
            daemon=True,
        )
        self._llm_probe_thread = thread
        thread.start()
        logger.log_info(
            f"{Icons.info} Started LLM registry probe worker for provider "
            f"'{self.llm_service_id}' every {self._llm_probe_interval_secs}s."
        )

    def _llm_probe_worker_loop(self) -> None:
        """Continuously probe unresolved registry entries on a background loop."""
        while not self._llm_probe_stop.is_set():
            try:
                self._probe_unresolved_llm_registry()
            except Exception as e:
                _log_exception("LLM registry probe worker failed", e)

            if self._llm_probe_stop.wait(max(1, self._llm_probe_interval_secs)):
                break

    def _probe_unresolved_llm_registry(self) -> None:
        """Probe unresolved registry entries and persist the derived metadata."""
        probe_db = None
        probe_rows = []
        try:
            probe_db = DBSession(
                wallet_zip_path="",
                verbose=False,
                user=self._user,
                password=self._password,
                dsn=self._dsn,
                config_dir=TNS_ADMIN,
            )
            probe_rows = probe_db.dict_sql_dataset(
                """
                select llm_id,
                       name,
                       provider,
                       model,
                       context_policy,
                       properties
                  from orac_api.llm_registry_v
                 where lower(context_policy) = 'unresolved'
                   and upper(is_enabled) = 'Y'
                 order by llm_id
                """
            )
            logger.log_info(
                f"{Icons.info} LLM probe worker discovered {len(probe_rows)} unresolved row(s)."
            )
        except Exception as e:
            _log_exception("Failed to load unresolved LLM registry rows", e)
            _close_db_session_quietly(probe_db)
            return

        for row in probe_rows:
            try:
                self._probe_single_llm_registry_row(probe_db, row)
            except Exception as e:
                _log_exception(
                    f"Failed to probe LLM registry row {row.get('LLM_ID')}",
                    e,
                )

        _close_db_session_quietly(probe_db)
        logger.log_info(
            f"{Icons.info} LLM registry probe pass complete: rows={len(probe_rows)}."
        )

    def _probe_single_llm_registry_row(
        self,
        db_session: DBSession,
        row: dict[str, Any],
    ) -> None:
        """Probe one unresolved registry row and persist the results."""
        llm_id = row.get("LLM_ID")
        provider = str(row.get("PROVIDER") or self.llm_service_id or "").strip().lower()
        model_name = str(row.get("MODEL") or "").strip()
        if llm_id in (None, "") or not provider or not model_name:
            return

        properties = row.get("PROPERTIES")
        service_url = self.service_url
        if isinstance(properties, dict):
            service_url = str(properties.get("service_url") or service_url).strip() or service_url
        elif isinstance(properties, str) and properties.strip():
            try:
                parsed_props = json.loads(properties)
            except Exception:
                parsed_props = {}
            if isinstance(parsed_props, dict):
                service_url = str(parsed_props.get("service_url") or service_url).strip() or service_url

        model_metadata = self._lookup_backend_model_metadata(model_name)

        if not self._is_chat_capable_llm_model(model_name):
            checked_on = iso_now()
            merged_properties = self._build_llm_registry_probe_properties(
                properties,
                history_probe_status="skipped_non_chat_model",
                supports_provider_history="N",
                suggested_context_policy="model",
                history_probe_checked_on=checked_on,
                first_response_ms=None,
                second_response_ms=None,
                total_response_ms=None,
                responsiveness_class="skipped",
                first_reply=None,
                second_reply=None,
                model_metadata=model_metadata,
            )

            with db_session.cursor() as cursor:
                cursor.execute(
                    """
                    update orac_api.llm_registry_v
                       set context_policy = :context_policy,
                           properties = json(:properties)
                     where llm_id = :llm_id
                    """,
                    {
                        "context_policy": "model",
                        "properties": merged_properties,
                        "llm_id": llm_id,
                    },
                )
                db_session.commit()
            return

        connector = self._get_llm_connector(
            service_id=provider,
            service_url=service_url,
            model_name=model_name,
        )

        probe_token = f"ORAC-PROBE-{llm_id}-{uuid.uuid4().hex[:8]}"
        first_prompt = (
            "Reply with the exact token "
            f"`{probe_token}` and nothing else."
        )
        second_prompt = (
            "Recent exchange (most recent at bottom):\n"
            f"USER: Reply with the exact token `{probe_token}` and nothing else.\n"
            f"ASSISTANT: {probe_token}\n\n"
            "USER (new message):\n"
            "What exact token did I ask you to repeat? Reply with the exact token only."
        )

        first_started = time.perf_counter()
        first_result = connector.send_prompt_with_meta(
            prompt_type="U",
            prompt=first_prompt,
            stream=False,
        )
        first_response_ms = int((time.perf_counter() - first_started) * 1000)
        first_reply = str(first_result.get("text") or "").strip()

        second_started = time.perf_counter()
        second_result = connector.send_prompt_with_meta(
            prompt_type="U",
            prompt=second_prompt,
            stream=False,
        )
        second_response_ms = int((time.perf_counter() - second_started) * 1000)
        second_reply = str(second_result.get("text") or "").strip()

        total_response_ms = first_response_ms + second_response_ms
        responsiveness_class = self._classify_probe_responsiveness(total_response_ms)
        supports_provider_history = "Y" if probe_token in second_reply else "N"
        suggested_context_policy = "app"
        history_probe_status = "complete"
        checked_on = iso_now()

        merged_properties = self._build_llm_registry_probe_properties(
            properties,
            history_probe_status=history_probe_status,
            supports_provider_history=supports_provider_history,
            suggested_context_policy=suggested_context_policy,
            history_probe_checked_on=checked_on,
            first_response_ms=first_response_ms,
            second_response_ms=second_response_ms,
            total_response_ms=total_response_ms,
            responsiveness_class=responsiveness_class,
            first_reply=first_reply,
            second_reply=second_reply,
            model_metadata=model_metadata,
        )

        with db_session.cursor() as cursor:
            cursor.execute(
                """
                update orac_api.llm_registry_v
                   set context_policy = :context_policy,
                       properties = json(:properties)
                 where llm_id = :llm_id
                """,
                {
                    "context_policy": suggested_context_policy,
                    "properties": merged_properties,
                    "llm_id": llm_id,
                },
            )
            db_session.commit()

    @staticmethod
    def _classify_probe_responsiveness(total_response_ms: int) -> str:
        """Classify probe responsiveness into the existing APEX LOV values."""
        if total_response_ms <= 0:
            return "fast"
        if total_response_ms < 2500:
            return "fast"
        if total_response_ms < 10000:
            return "normal"
        return "slow"

    @staticmethod
    def _is_chat_capable_llm_model(model_name: str) -> bool:
        """Return True for models that can participate in chat probes."""
        normalized = model_name.strip().lower()
        if not normalized:
            return False
        return "embed" not in normalized and "embedding" not in normalized

    @staticmethod
    def _build_llm_registry_probe_properties(
        existing_properties: Any,
        *,
        history_probe_status: str,
        supports_provider_history: str,
        suggested_context_policy: str,
        history_probe_checked_on: str,
        first_response_ms: int | None,
        second_response_ms: int | None,
        total_response_ms: int | None,
        responsiveness_class: str,
        first_reply: str | None,
        second_reply: str | None,
        model_metadata: dict[str, Any] | None = None,
    ) -> str:
        """Merge probe metadata into the registry properties JSON payload."""
        merged: dict[str, Any] = {}

        if isinstance(existing_properties, dict):
            merged.update(existing_properties)
        elif isinstance(existing_properties, str) and existing_properties.strip():
            try:
                parsed = json.loads(existing_properties)
            except Exception:
                parsed = {}
            if isinstance(parsed, dict):
                merged.update(parsed)

        merged.update(
            {
                "history_probe_status": history_probe_status,
                "supports_provider_history": supports_provider_history,
                "history_probe_suggested_context_policy": suggested_context_policy,
                "history_probe_checked_on": history_probe_checked_on,
                "history_probe_first_response_ms": first_response_ms,
                "history_probe_second_response_ms": second_response_ms,
                "history_probe_total_response_ms": total_response_ms,
                "history_probe_responsiveness_class": responsiveness_class,
                "history_probe_first_reply": first_reply,
                "history_probe_second_reply": second_reply,
            }
        )
        if model_metadata:
            merged.update(model_metadata)
        return json.dumps(merged, ensure_ascii=False, default=_json_default)

    def _init_plugin_routing(self) -> None:
        """Initialises plugin routing and performs normal startup bootstrap when enabled."""
        if not self._plugin_routing_enabled:
            logger.log_info(f"{Icons.info} Plugin routing disabled by configuration.")
            return

        try:
            embedding_model_id = self.config_mgr.config_value(
                "plugin_routing", "embedding_model_id", default="hash-embedding-v1"
            )
            embedding_dimensions = self.config_mgr.int_config_value(
                "plugin_routing", "embedding_dimensions", default=32
            )
            embedding_provider = HashEmbeddingProvider(
                model_id=embedding_model_id,
                dimensions=embedding_dimensions,
            )
            self.plugin_manager = PluginManager(embedding_provider=embedding_provider, logger=logger)
            self.plugin_router = PluginRouter(
                plugin_manager=self.plugin_manager,
                logger=logger,
                config_mgr=self.config_mgr,
                context_manager=self.ctx,
            )
            logger.log_info(f"{Icons.info} Plugin routing bootstrap starting.")
            logger.log_info(
                f"{Icons.tick} Plugin routing subsystem initialised with embedding model "
                f"'{embedding_provider.model_id}'."
            )
            if self._plugin_routing_bootstrap_on_startup:
                self.refresh_plugin_routing()
        except Exception as e:
            self.plugin_manager = None
            self.plugin_router = None
            self._plugin_routing_ready = False
            _log_exception("Plugin routing initialisation failed (non-fatal)", e)

    def refresh_plugin_routing(self) -> dict[str, Any] | None:
        """Bootstraps or refreshes plugin routing state on demand."""
        if not self._plugin_routing_enabled or self.plugin_manager is None:
            logger.log_info(f"{Icons.info} Plugin routing refresh skipped because subsystem is unavailable.")
            return None
        logger.log_info(f"{Icons.info} Plugin routing refresh requested.")
        report = self.plugin_manager.refresh()
        self._plugin_routing_ready = True
        logger.log_info(
            f"{Icons.info} Plugin routing refresh complete: "
            f"discovered={report.get('discovered', 0)} "
            f"enabled={report.get('enabled', 0)} "
            f"cache_hits={report.get('cache_hits', 0)} "
            f"re_embedded={report.get('re_embedded', 0)}"
        )
        return report

    def _ensure_plugin_routing_ready(self, *, force_refresh: bool = False) -> dict[str, Any] | None:
        """Ensures plugin routing is ready without rebuilding on every request."""
        if not self._plugin_routing_enabled or self.plugin_manager is None:
            logger.log_debug("Plugin routing unavailable; continuing without routing hints.")
            return None
        if self._plugin_routing_ready and not force_refresh:
            return self.plugin_manager.status()
        return self.refresh_plugin_routing()

    def _collect_plugin_routing_handoff(
        self,
        prompt: str,
        meta: dict,
    ) -> PluginRoutingHandoff | None:
        """Retrieves scored plugin candidates for downstream routing/selection."""
        if not self._plugin_routing_enabled or self.plugin_manager is None:
            logger.log_debug("Plugin routing disabled or not initialised; no routing candidates will be used.")
            return None

        force_refresh = bool((meta or {}).get("plugin_routing_refresh", False))
        if force_refresh:
            logger.log_info(f"{Icons.info} Plugin routing on-demand refresh requested by request metadata.")
        was_ready = self._plugin_routing_ready
        self._ensure_plugin_routing_ready(force_refresh=force_refresh)
        refreshed = bool(force_refresh or not was_ready)

        try:
            candidates = self.plugin_manager.find_candidates(
                prompt,
                top_n=self._plugin_routing_candidate_count,
                min_score=self._plugin_routing_min_score,
            )
        except Exception as e:
            _log_exception("Plugin routing candidate retrieval failed (non-fatal)", e)
            logger.log_debug("Continuing without plugin routing hints due to retrieval failure.")
            return None

        if not candidates:
            logger.log_debug("Plugin routing found no candidate plugins; using normal conversational flow.")
            return None

        logger.log_debug(f"Plugin routing produced {len(candidates)} candidate plugin(s).")
        logger.log_debug(
            "Plugin routing candidate scores: "
            + ", ".join(f"{candidate.plugin_id}={candidate.score:.4f}" for candidate in candidates)
        )

        return PluginRoutingHandoff(
            candidates=tuple(candidates),
            refreshed=refreshed,
        )

    def _apply_user_preference_meta(
        self,
        meta: dict[str, Any],
        auth_user: str,
    ) -> dict[str, Any]:
        """Overlay selected user preferences into request metadata."""
        enriched_meta = dict(meta)

        try:
            default_llm_pref = self.ctx.get_user_preference_value(
                username=auth_user,
                pref_key="default_llm_id",
            )
        except Exception as e:
            _log_exception("Failed to load default_llm_id preference", e)
            default_llm_pref = None

        default_llm_id: int | None = None
        if default_llm_pref not in (None, ""):
            try:
                default_llm_id = int(default_llm_pref)
            except Exception:
                logger.log_warning(
                    f"{Icons.warn} Ignoring non-numeric default_llm_id preference "
                    f"for user '{auth_user}': {default_llm_pref!r}"
                )
        if default_llm_id is not None:
            enriched_meta["default_llm_id"] = default_llm_id

        try:
            personality_pref = self.ctx.get_user_preference_value(
                username=auth_user,
                pref_key="personality_code",
            )
        except Exception as e:
            _log_exception("Failed to load personality_code preference", e)
            personality_pref = None

        personality_code = str(personality_pref or "DEFAULT").strip().upper()
        try:
            personality = self.ctx.get_orac_personality(personality_code)
            if not personality and personality_code != "DEFAULT":
                logger.log_warning(
                    f"{Icons.warn} Personality '{personality_code}' unavailable; falling back to DEFAULT."
                )
                personality = self.ctx.get_orac_personality("DEFAULT")
        except Exception as e:
            _log_exception("Failed to load selected Orac personality", e)
            personality = {}

        if personality:
            enriched_meta["personality_code"] = (
                str(personality.get("PERSONALITY_CODE") or personality_code)
                .strip()
                .upper()
            )
            enriched_meta["orac_personality"] = personality

        if meta.get("weather_location"):
            return enriched_meta

        try:
            weather_pref = self.ctx.get_user_preference_value(
                username=auth_user,
                pref_key="weather_location",
            )
        except Exception as e:
            _log_exception("Failed to load weather_location preference", e)
            return enriched_meta

        if not isinstance(weather_pref, dict):
            return enriched_meta

        name = str(weather_pref.get("name") or "").strip()
        if not name:
            return enriched_meta

        parts = [name]
        admin1 = str(weather_pref.get("admin1") or "").strip()
        country = str(weather_pref.get("country") or "").strip()
        if admin1:
            parts.append(admin1)
        if country:
            parts.append(country)

        enriched_meta["weather_location"] = ", ".join(parts)
        enriched_meta["weather_location_pref"] = weather_pref
        return enriched_meta

    def _get_llm_connector(
        self,
        *,
        service_id: str,
        service_url: str,
        model_name: str,
    ) -> Any:
        """Return a cached connector for the requested backend/model tuple."""
        key = (
            str(service_id or "").strip().lower(),
            str(service_url or "").strip(),
            str(model_name or "").strip(),
        )
        cached = self._llm_connector_cache.get(key)
        if cached is not None:
            return cached

        service_map = {
            "ollama": OllamaConnector,
            "lmstudio": LMStudioConnector,
        }
        connector_cls = service_map.get(key[0])
        if connector_cls is None:
            raise RuntimeError(f"Unsupported LLM service: {service_id}")

        connector = connector_cls(service_url=key[1], model_name=key[2])
        self._llm_connector_cache[key] = connector
        return connector

    def _registry_row_enabled(self, llm_row: dict[str, Any]) -> bool:
        """Return whether a registry row is enabled for conversational use."""
        if not llm_row:
            return False
        enabled = _as_bool(llm_row.get("IS_ENABLED"))
        return enabled is True

    def _backend_model_available(self, *, provider: str, model_name: str) -> bool:
        """Return whether the configured backend currently exposes a model."""
        provider_norm = str(provider or "").strip().lower()
        model_norm = str(model_name or "").strip()
        if not provider_norm or not model_norm:
            return False
        if provider_norm != self.llm_service_id.strip().lower():
            return False
        if model_norm in self._available_backend_models:
            return True
        return model_norm == self.model_name.strip()

    def _configured_model_lookup_candidates(self) -> list[str]:
        """Return model-name candidates for resolving the configured fallback row."""
        configured_model = str(self.model_name or "").strip()
        if not configured_model:
            return []

        candidates: list[str] = [configured_model]
        provider = self.llm_service_id.strip().lower()

        if provider == "ollama":
            if ":" not in configured_model:
                candidates.append(f"{configured_model}:latest")
            elif configured_model.endswith(":latest"):
                candidates.append(configured_model[: -len(":latest")])

        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.add(candidate)
                deduped.append(candidate)
        return deduped

    def _configured_fallback_registry_row(self) -> dict[str, Any]:
        """Resolve the registry row for the configured fallback model, tolerating aliases."""
        for candidate in self._configured_model_lookup_candidates():
            row = self.ctx.get_llm_registry_entry_by_provider_model(
                self.llm_service_id,
                candidate,
            )
            if row:
                if candidate != str(self.model_name or "").strip():
                    logger.log_info(
                        f"{Icons.info} Resolved configured model '{self.model_name}' "
                        f"to registry entry '{candidate}'."
                    )
                return row
        return {}

    def _configured_fallback_selection(
        self,
        *,
        warning_message: str | None = None,
    ) -> dict[str, Any]:
        """Return the configured runtime model selection, with registry row if present."""
        if warning_message:
            logger.log_warning(warning_message)

        fallback_row = self._configured_fallback_registry_row()
        resolved_model_name = (
            str(fallback_row.get("MODEL") or "").strip()
            if fallback_row
            else self.model_name
        )
        selection = {
            "llm_id": fallback_row.get("LLM_ID") if fallback_row else None,
            "provider": self.llm_service_id,
            "model_name": resolved_model_name,
            "service_url": self.service_url,
            "source": "configured_fallback",
            "registry_row": fallback_row,
        }
        if not fallback_row:
            logger.log_warning(
                f"{Icons.warn} Configured fallback model '{self.model_name}' "
                f"for provider '{self.llm_service_id}' has no registry row; "
                f"conversation llm_id will remain null."
            )
        return selection

    def _resolve_new_conversation_llm(
        self,
        *,
        auth_user: str,
        meta: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve the LLM to persist when creating a new conversation."""
        preferred_llm_id = meta.get("default_llm_id")
        if preferred_llm_id in (None, ""):
            return self._configured_fallback_selection()

        llm_row = self.ctx.get_llm_registry_entry(preferred_llm_id)
        if not llm_row:
            return self._configured_fallback_selection(
                warning_message=(
                    f"{Icons.warn} User '{auth_user}' selected default_llm_id "
                    f"{preferred_llm_id}, but no registry row exists. "
                    f"Falling back to configured model '{self.model_name}'."
                )
            )

        provider = str(llm_row.get("PROVIDER") or "").strip().lower()
        model_name = str(llm_row.get("MODEL") or "").strip()
        if not self._registry_row_enabled(llm_row):
            return self._configured_fallback_selection(
                warning_message=(
                    f"{Icons.warn} User '{auth_user}' selected disabled LLM "
                    f"'{model_name}' (llm_id={llm_row.get('LLM_ID')}). "
                    f"Falling back to configured model '{self.model_name}'."
                )
            )

        if not self._backend_model_available(provider=provider, model_name=model_name):
            return self._configured_fallback_selection(
                warning_message=(
                    f"{Icons.warn} User '{auth_user}' selected unavailable LLM "
                    f"'{model_name}' (provider='{provider}', llm_id={llm_row.get('LLM_ID')}). "
                    f"Falling back to configured model '{self.model_name}'."
                )
            )

        return {
            "llm_id": llm_row.get("LLM_ID"),
            "provider": provider,
            "model_name": model_name,
            "service_url": self.service_url,
            "source": "user_preference",
            "registry_row": llm_row,
        }

    def _resolve_effective_llm(
        self,
        *,
        session_id: str,
        auth_user: str,
        created_new_conversation: bool,
        new_conversation_selection: dict[str, Any],
    ) -> dict[str, Any]:
        """Resolve the effective runtime LLM for a concrete conversation session."""
        stored_llm_id = self.ctx.get_conversation_llm_id(session_id)
        if stored_llm_id is None:
            if created_new_conversation:
                return dict(new_conversation_selection)
            return self._configured_fallback_selection()

        llm_row = self.ctx.get_llm_registry_entry(stored_llm_id)
        if not llm_row:
            return self._configured_fallback_selection(
                warning_message=(
                    f"{Icons.warn} Conversation '{session_id}' for user '{auth_user}' "
                    f"references missing llm_id={stored_llm_id}. "
                    f"Using configured model '{self.model_name}' at runtime."
                )
            )

        provider = str(llm_row.get("PROVIDER") or "").strip().lower()
        model_name = str(llm_row.get("MODEL") or "").strip()
        if not self._registry_row_enabled(llm_row):
            return self._configured_fallback_selection(
                warning_message=(
                    f"{Icons.warn} Conversation '{session_id}' for user '{auth_user}' "
                    f"references disabled LLM '{model_name}' (llm_id={stored_llm_id}). "
                    f"Using configured model '{self.model_name}' at runtime."
                )
            )

        if not self._backend_model_available(provider=provider, model_name=model_name):
            return self._configured_fallback_selection(
                warning_message=(
                    f"{Icons.warn} Conversation '{session_id}' for user '{auth_user}' "
                    f"references unavailable LLM '{model_name}' (provider='{provider}', llm_id={stored_llm_id}). "
                    f"Using configured model '{self.model_name}' at runtime."
                )
            )

        return {
            "llm_id": llm_row.get("LLM_ID"),
            "provider": provider,
            "model_name": model_name,
            "service_url": self.service_url,
            "source": "conversation",
            "registry_row": llm_row,
        }

    def _estimate_tokens(self, text: str) -> int:
        """
        Very rough token estimate that works across local models:
        ~4 chars per token for English-ish text, fall back to length-based.
        """
        if not text:
            return 0
        # Trim extremes to avoid huge counts from logs/pastes
        L = len(text)
        # Fast heuristic: 1 token ≈ 4 characters
        est = max(1, L // 4)
        return est

    def _select_dialog_under_budget(self, all_msgs: list[dict], *, budget_tokens: int) -> list[dict]:
        """
        From a message list like [{'role': 'user'|'assistant'|...,'content': '...'}, ...],
        keep only user/assistant messages and walk backward until we exceed the budget.
        We include the message that tips us over (to avoid dropping the immediate prior turn),
        then return the slice in chronological order.
        """
        dialog = [m for m in all_msgs if (m.get("role") in ("user", "assistant"))]

        total = 0
        picked_rev: list[dict] = []

        for m in reversed(dialog):
            c = (m.get("content") or "").strip()
            # Base weight: content tokens; add a tiny role header overhead
            cost = self._estimate_tokens(c) + 4
            total += cost
            picked_rev.append(m)
            if total >= budget_tokens:
                break

        return list(reversed(picked_rev))

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
        Build a stable session id.
        Priority:
          1) explicit meta.session_id (if provided)
          2) scope == 'user'         -> '<user>'
          3) scope == 'user+client'  -> '<user>::<client>'
        """
        sid = (meta or {}).get("session_id")
        if isinstance(sid, str) and sid.strip():
            return sid.strip()

        # normalize user
        try:
            u = (auth_user or "unknown").strip().lower()
        except Exception:
            u = str(auth_user or "unknown").strip().lower()

        if self._session_scope == "user":
            session_id = u
        else:
            raw_client = (meta or {}).get("client", "unknown")
            c = self._normalize_client_id(raw_client) if self._normalize_client else str(
                raw_client or "unknown").strip().lower()
            session_id = f"{u}::{c}"

        # Log once in a while for visibility
        try:
            logger.log_debug(f"{Icons.info} session_scope={self._session_scope} derived session_id_base='{session_id}'")
        except Exception:
            pass

        return session_id

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

    def _handle_persistence_failure(self, phase: str, exc: BaseException) -> None:
        """Record and log persistence failures for diagnostics and tests."""
        failure = {
            "phase": phase,
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        failures = getattr(self, "_persistence_failures", None)
        if failures is None:
            self._persistence_failures = []
            failures = self._persistence_failures
        failures.append(failure)
        _log_exception(f"Failed to persist {phase}", exc)
        if self._is_recoverable_db_disconnect(exc):
            try:
                self._refresh_db_session()
            except Exception as reconnect_exc:
                _log_exception(
                    "Follow-up Oracle reconnect after persistence failure failed",
                    reconnect_exc,
                )
        if getattr(self, "_fail_on_persistence_error", False):
            raise RuntimeError(
                f"Persistence failure during {phase}: {exc}"
            ) from exc

    @staticmethod
    def _is_recoverable_db_disconnect(exc: BaseException) -> bool:
        """Return whether an exception represents a recoverable Oracle disconnect."""
        text = str(exc)
        return any(
            token in text
            for token in (
                "DPY-1001",
                "DPY-4011",
                "DPI-1010",
                "ORA-03113",
                "ORA-03114",
            )
        )

    @staticmethod
    def _is_unregistered_user_error(exc: BaseException) -> bool:
        """Return whether an exception represents an unregistered runtime user."""
        return isinstance(exc, PermissionError) and "not registered" in str(exc)

    def _refresh_db_session(self) -> None:
        """Recreate the owned DB session and rebind it into the context layer."""
        logger.log_warning(
            f"{Icons.warn} Reconnecting Oracle session for Orac runtime."
        )
        new_session = DBSession(
            wallet_zip_path="",
            verbose=True,
            user=self._user,
            password=self._password,
            dsn=self._dsn,
            config_dir=TNS_ADMIN,
        )
        old_session = getattr(self, "db_session", None)
        self.db_session = new_session
        if getattr(self, "ctx", None) is not None:
            self.ctx.db = new_session
        if old_session is not None:
            try:
                old_session.close()
            except Exception:
                logger.log_debug("Ignored close failure on stale Oracle session.")

    def _ensure_db_session_ready(self) -> None:
        """Validate the Oracle session and reconnect once if it has gone stale."""
        db_session = getattr(self, "db_session", None)
        if db_session is None:
            return
        try:
            db_session.fetch_as_lists("select 1 from dual")
        except Exception as exc:
            if not self._is_recoverable_db_disconnect(exc):
                raise
            _log_exception("Oracle session health check failed; reconnecting", exc)
            self._refresh_db_session()
            self.db_session.fetch_as_lists("select 1 from dual")

    def _save_assistant_turn(
        self,
        session_id: str,
        auth_user: str,
        content: str,
        *,
        client: str,
        req_id: str | None,
        show_reasoning: bool,
        llm_id: int | None = None,
        tokens_used: int | None = None,
        request_flags: dict[str, bool] | None = None,
    ) -> int:
        """Persists an assistant turn and returns the new turn index if available."""
        asst_meta = {
            "client": client,
            "protocol_version": PROTOCOL_VERSION,
            "ts": iso_now(),
            "req_id": req_id,
            "show_reasoning": show_reasoning,
        }
        try:
            save_res_a = self.ctx.save_assistant_turn(
                session_id,
                auth_user,
                content,
                meta=asst_meta,
                llm_id=llm_id,
                tokens_used=tokens_used,
            )
            logger.log_debug(f"Saved assistant msg: {save_res_a}")
            return int(save_res_a.get("turn_index", 0))
        except Exception as e:
            if request_flags is not None and self._is_unregistered_user_error(e):
                request_flags["anonymous_user"] = True
            self._handle_persistence_failure("assistant_turn", e)
            return 0

    # --- Response builder -----------------------------------------------------
    def _build_response(self, req_env: dict, content: str, *,
                        stop_reason: str = "stop",
                        prompt_tokens: int = 0,
                        completion_tokens: int = 0,
                        model_name: str | None = None,
                        user_registration: str = "registered") -> dict:
        """Build a protocol-compliant non-streaming response envelope."""
        response_model = str(model_name or self.model_name)
        resp = {
            "v": 1,
            "type": "response",
            "id": new_id("res"),
            "reply_to": req_env.get("id"),
            "ts": iso_now(),
            "route": req_env.get("route", "orac.prompt"),
            "meta": {
                "status": "ok",
                "model": response_model,
                "req_id": req_env.get("id"),
                "user_registration": user_registration,
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

    def _maybe_set_conversation_title(self, session_id: str, meta: dict, llm_connector: Any) -> None:
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

            raw = llm_connector.send_prompt(prompt_type="U", prompt=title_prompt, stream=False)
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
            # Guard against drifting session ids from the caller
            if not self._allow_external_session_id and "session_id" in meta:
                dropped = meta.get("session_id")
                meta = dict(meta)  # shallow copy
                meta.pop("session_id", None)
                logger.log_debug(
                    f"{Icons.warn} Dropped external meta.session_id='{dropped}' (using internal derivation)")

            show_reasoning = bool(meta.get("show_reasoning", not self.strip_reasoning_tags))
            client = meta.get("client", "unknown")
            auth_user = getattr(auth_res, "user", "unknown")

            try:
                self._ensure_db_session_ready()
            except Exception as e:
                _log_exception("Oracle session validation failed (non-fatal)", e)

            meta = self._apply_user_preference_meta(meta, auth_user)

            logger.log_info(f"{Icons.info} [{client}] user={auth_user} Prompt received")
            logger.log_debug(f"Prompt text: {prompt}")
            logger.log_info(f"meta.show_reasoning={show_reasoning} (strip_reasoning_default={self.strip_reasoning_tags})")
            request_flags = {"anonymous_user": False}

            # --- Session + conversation (timeout-aware) ---------------------------------
            logger.log_debug(
                f"{Icons.info} sid-derive inputs: allow_ext={self._allow_external_session_id} "
                f"scope={self._session_scope} normalize_client={self._normalize_client} "
                f"auth_user='{auth_user}' raw_client='{meta.get('client', '')}' "
                f"ext_sid_present={'session_id' in (req_env.get('meta') or {})}"
            )

            session_id_base = self._derive_session_id(meta, auth_user)

            session_id_base = self._derive_session_id(meta, auth_user)
            logger.log_debug(f"{Icons.tick} derived session_id_base='{session_id_base}'")
            new_conversation_selection = self._resolve_new_conversation_llm(
                auth_user=auth_user,
                meta=meta,
            )

            # Prefer timeout-aware conversation rollover. If anything goes wrong,
            # fall back to the non-timeout path and keep going.
            try:
                roll = self.ctx.ensure_conversation_with_timeout(
                    user_name=auth_user,
                    session_id_base=session_id_base,
                    llm_id=new_conversation_selection.get("llm_id"),
                    timeout_seconds=self._conversation_timeout_secs,
                )

                try:
                    la = float(roll.get("last_activity_epoch", 0.0))
                    age = float(roll.get("age_seconds", -1.0))
                    logger.log_debug(
                        f"{Icons.info} conv-timeout check: sid_base='{session_id_base}' "
                        f"timeout={self._conversation_timeout_secs}s age={age:.1f}s last_ts={la:.0f}"
                    )
                except Exception:
                    pass

                # Use the (possibly rolled-over) session_id from now on
                session_id = roll.get("session_id", session_id_base)
                created_new_conversation = bool(roll.get("rolled_over"))
                if roll.get("rolled_over"):
                    logger.log_info(
                        f"{Icons.info} Conversation rollover: base={session_id_base} -> new={session_id} "
                        f"(timeout={self._conversation_timeout_secs}s)"
                    )
                    try:
                        la = float(roll.get("last_activity_epoch", 0.0))
                        age = float(roll.get("age_seconds", -1.0))
                        logger.log_debug(
                            f"{Icons.info} conv-timeout check: sid_base='{session_id_base}' "
                            f"timeout={self._conversation_timeout_secs}s age={age:.1f}s last_ts={la:.0f}"
                        )
                    except Exception:
                        pass

                    # Transition old conversation state if configured
                    try:
                        previous_session_id = roll.get("previous_session_id") or session_id_base
                        if getattr(self, "_archive_on_rollover", False):
                            self.ctx.archive_conversation(previous_session_id)
                            logger.log_info(f"{Icons.box} Archived prior conversation: {previous_session_id}")
                        elif getattr(self, "_close_on_rollover", True):
                            self.ctx.close_conversation(previous_session_id)
                            logger.log_info(f"{Icons.stop} Closed prior conversation: {previous_session_id}")
                        else:
                            logger.log_debug(f"{Icons.info} Prior conversation left 'open': {previous_session_id}")
                    except Exception as e_state:
                        _log_exception("State transition on rollover failed (non-fatal)", e_state)
                else:
                    logger.log_debug(f"{Icons.tick} Using existing conversation for {session_id}")
            except Exception as e:
                if self._is_unregistered_user_error(e):
                    request_flags["anonymous_user"] = True
                _log_exception("ensure_conversation_with_timeout failed (non-fatal)", e)
                session_id = session_id_base
                created_new_conversation = False
                try:
                    existing_llm_id = self.ctx.get_conversation_llm_id(session_id)
                    if existing_llm_id is None:
                        self.ctx.ensure_conversation(
                            user_name=auth_user,
                            session_id=session_id,
                            llm_id=new_conversation_selection.get("llm_id"),
                        )
                        created_new_conversation = True
                    else:
                        self.ctx.ensure_conversation(
                            user_name=auth_user,
                            session_id=session_id,
                            llm_id=existing_llm_id,
                        )
                except Exception as e2:
                    if self._is_unregistered_user_error(e2):
                        request_flags["anonymous_user"] = True
                    _log_exception("ensure_conversation fallback failed (non-fatal)", e2)

            selected_personality_code = str(
                meta.get("personality_code") or "DEFAULT"
            ).strip().upper()
            if not created_new_conversation:
                try:
                    conversation_personality_code = self.ctx.get_conversation_personality_code(
                        session_id
                    )
                except Exception as e:
                    _log_exception(
                        "Failed to read conversation personality for reuse check",
                        e,
                    )
                    conversation_personality_code = None

                if conversation_personality_code != selected_personality_code:
                    logger.log_info(
                        f"{Icons.info} Persona change detected for session '{session_id}': "
                        f"stored='{conversation_personality_code or 'UNKNOWN'}', "
                        f"selected='{selected_personality_code}'. Starting a new conversation."
                    )
                    try:
                        if getattr(self, "_archive_on_rollover", False):
                            self.ctx.archive_conversation(session_id)
                            logger.log_info(f"{Icons.box} Archived prior conversation: {session_id}")
                        else:
                            self.ctx.close_conversation(session_id)
                            logger.log_info(f"{Icons.stop} Closed prior conversation: {session_id}")
                    except Exception as e_state:
                        _log_exception(
                            "Failed to transition prior conversation during persona rollover",
                            e_state,
                        )

                    session_id = new_session_id(session_id_base)
                    self.ctx.ensure_conversation(
                        user_name=auth_user,
                        session_id=session_id,
                        llm_id=new_conversation_selection.get("llm_id"),
                    )
                    created_new_conversation = True

            effective_llm = self._resolve_effective_llm(
                session_id=session_id,
                auth_user=auth_user,
                created_new_conversation=created_new_conversation,
                new_conversation_selection=new_conversation_selection,
            )
            llm_connector = self._get_llm_connector(
                service_id=str(effective_llm.get("provider") or self.llm_service_id),
                service_url=str(effective_llm.get("service_url") or self.service_url),
                model_name=str(effective_llm.get("model_name") or self.model_name),
            )
            effective_llm_id = effective_llm.get("llm_id")
            if effective_llm_id is not None:
                try:
                    effective_llm_id = int(effective_llm_id)
                except Exception:
                    effective_llm_id = None
            effective_model_name = str(effective_llm.get("model_name") or self.model_name)
            logger.log_info(
                f"{Icons.info} Effective LLM for session '{session_id}': "
                f"model='{effective_model_name}', provider='{effective_llm.get('provider')}', "
                f"llm_id={effective_llm_id}, source='{effective_llm.get('source')}'"
            )

            # --- Ensure a system primer is stored once per conversation ---------
            try:
                if self.ctx.last_turn_index(session_id) == 0:
                    primer = _orac_system_primer(
                        {
                            "reply_language": meta.get(
                                "reply_language",
                                self._reply_language,
                            ),
                            "orac_personality": meta.get("orac_personality"),
                        },
                        self._system_prompt_policy,
                    )
                    self.ctx.save_system_turn(session_id, auth_user, primer, meta={
                        "kind": "primer",
                        "ts": iso_now(),
                        "protocol_version": PROTOCOL_VERSION,
                        "personality_code": str(
                            meta.get("personality_code") or "DEFAULT"
                        ).strip().upper(),
                    }, llm_id=effective_llm_id)
            except Exception as e:
                if self._is_unregistered_user_error(e):
                    request_flags["anonymous_user"] = True
                self._handle_persistence_failure("system_primer", e)

            # --- Save USER turn -------------------------------------------------
            user_meta = {
                "client": client,
                "protocol_version": PROTOCOL_VERSION,
                "ts": iso_now(),
                "req_id": req_env.get("id"),
            }
            try:
                save_res_u = self.ctx.save_user_turn(
                    session_id,
                    auth_user,
                    prompt,
                    meta=user_meta,
                    llm_id=effective_llm_id,
                )
                logger.log_debug(f"Saved user msg: {save_res_u}")
            except Exception as e:
                if self._is_unregistered_user_error(e):
                    request_flags["anonymous_user"] = True
                self._handle_persistence_failure("user_turn", e)

            plugin_routing_handoff = self._collect_plugin_routing_handoff(prompt, meta)
            plugin_execution_result = None
            if self.plugin_router is not None:
                plugin_execution_result = self.plugin_router.route(
                    prompt,
                    meta,
                    plugin_routing_handoff,
                    auth_user,
                )

            if plugin_execution_result is not None and plugin_execution_result.handled:
                content = plugin_execution_result.content
                # TODO: Persist plugin_result separately from assistant_response once
                # context/message provenance is introduced explicitly.
                last_ti = self._save_assistant_turn(
                    session_id,
                    auth_user,
                    content,
                    client=client,
                    req_id=req_env.get("id"),
                    show_reasoning=show_reasoning,
                    llm_id=effective_llm_id,
                    request_flags=request_flags,
                )
                self._maybe_set_conversation_title(session_id, meta, llm_connector)
                self._maybe_prune(session_id, last_ti)
                resp_env = self._build_response(
                    req_env,
                    content,
                    stop_reason=plugin_execution_result.stop_reason,
                    prompt_tokens=0,
                    completion_tokens=0,
                    model_name=effective_model_name,
                    user_registration=(
                        "anonymous" if request_flags["anonymous_user"] else "registered"
                    ),
                )
                return json.dumps(resp_env, ensure_ascii=False)

            # --- Build context-primed prompt -----------------------------------
            final_prompt = self._build_contextual_prompt(
                session_id,
                prompt,
                meta,
                auth_user,
                plugin_routing_handoff=plugin_routing_handoff,
            )
            short = (final_prompt[:1200] + " …") if len(final_prompt) > 1200 else final_prompt
            logger.log_info(f"{Icons.info} Final prompt (truncated): {short}")
            if self.enable_prompt_dump:
                _dump_debug_blob("final-prompt", final_prompt)

            # === Call backend (non-streaming path) ===
            try:
                prompt_result = llm_connector.send_prompt_with_meta(
                    prompt_type="U",
                    prompt=final_prompt,
                    stream=False,
                )
            except Exception as e:
                _log_exception("LLM backend call failed", e)
                err = {
                    "v": 1, "type": "response", "id": new_id("res"),
                    "reply_to": req_env.get("id"), "ts": iso_now(), "route": "orac.prompt",
                    "meta": {"status": "error", "model": effective_model_name, "req_id": req_env.get("id")},
                    "payload": None,
                    "error": {"code": "LLM_BACKEND_ERROR", "message": str(e)},
                }
                return json.dumps(err, ensure_ascii=False)

            # Normalise: ensure string
            raw = str(prompt_result.get("text") or "").strip()
            prompt_tokens = int(prompt_result.get("prompt_tokens") or 0)
            completion_tokens = int(prompt_result.get("completion_tokens") or 0)
            total_tokens = int(prompt_result.get("total_tokens") or 0)

            # Apply local reasoning-strip unless explicitly requested
            if show_reasoning:
                content = raw
            else:
                stripped = self._strip_reasoning_tags(raw)
                content = stripped if stripped else raw

            if not content:
                logger.log_warning("Backend returned empty content after stripping; using friendly fallback.")
                content = "Hello! 👋"

            # --- Save ASSISTANT turn -------------------------------------------
            last_ti = self._save_assistant_turn(
                session_id,
                auth_user,
                content,
                client=client,
                req_id=req_env.get("id"),
                show_reasoning=show_reasoning,
                llm_id=effective_llm_id,
                tokens_used=total_tokens or None,
                request_flags=request_flags,
            )

            self._maybe_set_conversation_title(session_id, meta, llm_connector)
            self._maybe_prune(session_id, last_ti)

            resp_env = self._build_response(
                req_env,
                content,
                stop_reason="stop",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model_name=effective_model_name,
                user_registration=(
                    "anonymous" if request_flags["anonymous_user"] else "registered"
                ),
            )

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
