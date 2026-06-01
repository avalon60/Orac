"""Oracle orchestrator, orac.py (protocol-enabled, non-streaming response)"""

# Author: Clive Bostock
# Date: 2026-04-29
# Description: Orac runtime orchestration, including conversation-aware LLM
#   selection and fallback handling.

import asyncio
import re
import json
import hashlib
import threading
import uuid
import os
import time
import sys
import traceback
from collections.abc import AsyncIterator, Awaitable, Callable
from decimal import Decimal
from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo
import yaml

from model.network import OracListener
from model.llm_connector import LLMUsageMetadata
from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from lib.icons import Icons
from lib.logutil import Logger
from lib.protocol_validation import disabled_protocol_validator
from model.orac_auth import FrameAuthChain, ZenFrameAuth
from model.context_manager import OracContextManager
from model.text_chunker import TextChunker
from orac_voice.tts_coalescer import TtsChunkCoalescer
from orac_voice.tts_coalescer import DEFAULT_TTS_COALESCE_MAX_CHARS
from orac_voice.tts_coalescer import DEFAULT_TTS_COALESCE_MIN_CHUNKS
from orac_voice.tts_worker import TtsWorker
from orac_voice.tts_worker import create_local_tts_worker_from_config
from orac_voice.tts_voice_catalog import refresh_tts_voice_catalog
from orac_voice.tts_voice_catalog import resolve_tts_voice_selection
from orac_voice.voice_events import VoiceEvent
from model.plugin_audit_adapter import PluginAuditAdapter
from model.plugin_routing import (
    HashEmbeddingProvider,
    PluginManager,
    PluginRoutingHandoff,
    render_plugin_routing_hints,
)
from model.plugin_execution_service import PluginExecutionService
from model.plugin_confirmation_broker import PluginConfirmationBroker
from model.plugin_router import PluginRouter
from model.plugin_service_manager import PluginServiceManager
from model.provider_registry import ProviderRegistry
from orac_core.retrieval import ExplicitRetrievalService
from orac_core.retrieval import GroundingPack
from orac_core.retrieval import GroundingPackBuilder
from orac_core.retrieval import RetrievalDecisionService
from orac_core.retrieval import RetrievalOutcome
from orac_core.retrieval import RetrievalTurnContext
from orac_core.retrieval import build_topic_signature
from orac_core.retrieval import build_retrieval_response_guidance
from orac_core.retrieval import SearXNGSearchProvider
from orac_core.retrieval import SearchBroker
from orac_core.retrieval import normalize_retrieval_response_style
from orac_core.retrieval import polish_retrieval_response_text
from orac_core.retrieval import SourceFetcher
from orac_core.retrieval import SearchRequest
from orac_core.retrieval import detect_explicit_search_request
from lib.session_manager import DBSession
from lib.user_security import UserSecurity


class _VoicePlaybackSubscription:
    """Thread-safe callback wrapper for one active voice prompt stream."""

    def __init__(self, *, callback: Callable[[dict[str, Any]], None]) -> None:
        """Initialise the subscription."""
        self.callback = callback
        self.playback_expected = False
        self.playback_started = False
        self.playback_queued = 0
        self.playback_finished = 0
        self.playback_terminal = False


VOICE_PLAYBACK_START_TIMEOUT_SECONDS = 120.0
VOICE_PLAYBACK_FINISH_TIMEOUT_SECONDS = 120.0


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

StreamEventSink = Callable[[dict[str, Any]], Awaitable[None]]

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
        logger.log_warning(f"⚠️ Local schema fallback failed: {e2}")
        validate_frame, PROTOCOL_VERSION = disabled_protocol_validator(e2)
        logger.log_warning(
            "⚠️ Protocol validation disabled by explicit development override."
        )

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
        f"Session timezone preference: {tz_name}.",
        f"User-facing local time: {local_str}; day: {dow}.",
        "The user-facing local time is authoritative for the current turn; "
        "do not infer the current time from conversation history or "
        "client/request timestamps.",
        "When answering questions about the current time or date, use the "
        "user-facing local time above, not UTC.",
        "For direct questions like 'what time is it?', answer with the exact "
        "HH:MM value from the user-facing local time. Do not round to the "
        "hour or omit minutes unless the user explicitly asks for an "
        "approximate time.",
        f"Current UTC time for logs and technical timestamps only: {utc_iso}.",
    ]
    if weather_location:
        lines.append(f"Assume your current location is {weather_location}.")
        lines.append(
            "This weather location is the preferred location context; do not "
            "replace it with a location inferred from the timezone."
        )
        lines.append(
            "If asked where you are, where you are located, or similar, answer "
            "with this configured operational/home location. Do not answer that "
            "you lack a physical location unless the user explicitly asks about "
            "physical embodiment."
        )
    else:
        lines.append(
            f"No explicit weather location is set. Assume your current location is "
            f"{_timezone_location_label(tz_name)} based on the session timezone."
        )
        lines.append(
            "If asked where you are, where you are located, or similar, answer "
            "with this inferred operational/home location. Do not answer that "
            "you lack a physical location unless the user explicitly asks about "
            "physical embodiment."
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


SYSTEM_GENERATION_DEFAULTS: dict[str, Any] = {
    "temperature": 0.2,
    "repeat_penalty": 1.1,
}

GENERATION_PRESET_FIELDS = (
    "TEMPERATURE",
    "TOP_P",
    "TOP_K",
    "REPEAT_PENALTY",
    "NUM_PREDICT",
    "SEED",
)


def _generation_options_from_preset(preset: dict[str, Any]) -> dict[str, Any]:
    """Extract provider-neutral generation options from a preset row."""
    if not isinstance(preset, dict):
        return {}

    options: dict[str, Any] = {}
    for field in GENERATION_PRESET_FIELDS:
        value = preset.get(field)
        if value is not None:
            options[field.lower()] = value
    return options


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
    creator_profile = identity.get("creator_profile", {})
    if not isinstance(creator_profile, dict):
        creator_profile = {}
    creator_name = str(creator_profile.get("name") or "").strip()
    creator_role = str(creator_profile.get("role") or "").strip()
    identity_answer = (
        f"I am {assistant_name}, an extensible artificial intelligence system"
    )
    if creator_name:
        identity_answer = f"{identity_answer}, created by {creator_name}"
    identity_answer_policy = str(
        identity.get("identity_answer_policy")
        or (
            "Your name is {assistant_name}. Only answer with the identity "
            "statement when the user explicitly asks who or what you are, who "
            "created you, or another direct identity/creator question. For "
            "those questions, answer simply: \"{identity_answer}.\" Do not "
            "include {assistant_name}'s identity or creator in replies to "
            "ordinary factual requests such as date, time, weather, "
            "calculations, or status questions unless the user asks for it."
        )
    ).strip()
    lines.append(
        identity_answer_policy.replace(
            "{assistant_name}",
            assistant_name,
        ).replace(
            "{identity_answer}",
            identity_answer,
        )
    )

    if creator_name:
        if creator_role:
            lines.append(
                f"{assistant_name} was created by "
                f"{creator_name}, {creator_role}."
            )
        else:
            lines.append(f"{assistant_name} was created by {creator_name}.")
    lines.append(
        "Do not volunteer details about Orac's implementation, underlying "
        "model, runtime, training, or vendor provenance."
    )
    lines.append(
        "If asked whether Orac was created, trained, or operated by a "
        "third-party model vendor, answer no without listing vendor names."
    )
    lines.append(
        "Only if asked specifically about technical implementation details, "
        "say Orac is running on the configured local model/runtime."
    )
    lines.append(
        "Do not infer or invent model provenance, and do not add vendor "
        "denials to ordinary identity answers."
    )

    notable_works = creator_profile.get("notable_works", [])
    if notable_works:
        works_text = "; ".join(
            str(item).strip() for item in notable_works if str(item).strip()
        )
        if works_text:
            lines.append(f"Creator profile notable works: {works_text}.")

    lines.extend(
        str(rule) for rule in identity.get("rules", []) if str(rule).strip()
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


def _system_prompt_fingerprint(primer: str) -> str:
    """Return a stable fingerprint for a rendered system primer."""
    return hashlib.sha256(primer.encode("utf-8")).hexdigest()


# ==============================================================================
# Orac Orchestrator
# ==============================================================================
class Orac:
    """
    Orac is the AI orchestrator that routes messages to the LLM and skills system.
    """
    def __init__(self):
        logger.log_info("Instantiating Orac...")
        self._tts_worker: TtsWorker | None = None
        self._voice_cancelled_turns: set[tuple[str, str]] = set()
        self._voice_event_subscribers: dict[
            tuple[str, str],
            list[_VoicePlaybackSubscription],
        ] = {}
        self._voice_event_subscriber_lock = threading.Lock()
        try:
            self.config_mgr = ConfigManager(config_file_path=CONFIG_FILE_PATH)
            self.llm_service_id = self.config_mgr.config_value("service", "llm_service_id")
            self.model_name = self.config_mgr.config_value("service", "default_model_name")
            self.service_url = self.config_mgr.config_value("service", "service_url")
            self.provider_registry = ProviderRegistry(logger=logger)
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
            self._default_timezone = (
                self.config_mgr.config_value("context", "timezone", default="Europe/London").strip()
                or "Europe/London"
            )
            self._retrieval_response_style = normalize_retrieval_response_style(
                self.config_mgr.config_value(
                    "retrieval",
                    "retrieval_response_style",
                    default="normal",
                )
            )
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

            self._validate_or_pull_model()
            try:
                self.llm = self.provider_registry.create_connector(
                    provider_id=self.llm_service_id,
                    service_url=self.service_url,
                    model_name=self.model_name,
                )
            except ValueError as exc:
                message = f"{Icons.error} LLM service not implemented: {self.llm_service_id}"
                logger.log_critical(message)
                raise NotImplementedError(message) from exc

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
            db_connection_name = self.config_mgr.config_value(
                section="database",
                key="connection_name",
                default="orac-service",
            )
            user_sec = UserSecurity(project_identifier=project_id, resource_type="dsn")
            self._user, self._password, self._dsn = user_sec.named_connection_creds(
                connection_name=db_connection_name
            )

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
            self._refresh_tts_voice_catalog()
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
            self.plugin_execution_service: PluginExecutionService | None = None
            self.plugin_audit_adapter: PluginAuditAdapter | None = None
            self.plugin_confirmation_broker: PluginConfirmationBroker | None = None
            self.plugin_service_manager: PluginServiceManager | None = None
            self.retrieval_service: ExplicitRetrievalService | None = None
            self.retrieval_decision_service: RetrievalDecisionService | None = None
            self._retrieval_context_by_session: dict[str, RetrievalTurnContext] = {}
            self._plugin_routing_ready = False
            self._init_plugin_routing()
            self._init_retrieval()
            self._init_voice_output()

            logger.log_info(f"{Icons.robot} Orac orchestrator initialized with model: {self.model_name}")
            logger.log_info(f"{Icons.settings} Reasoning tags stripped by default: {self.strip_reasoning_tags}")
            logger.log_info(f"{Icons.docs} Protocol version: {PROTOCOL_VERSION}")

        except Exception as e:
            _log_exception("Fatal error during Orac initialization", e)
            raise

    def _init_voice_output(self) -> None:
        """Initialise optional local voice output from Orac configuration."""
        try:
            self._tts_worker = create_local_tts_worker_from_config(
                event_handler=self._handle_voice_event,
            )
            if self._tts_worker is None:
                return
            self._tts_coalescer = self._create_tts_coalescer()
            self._tts_worker.start()
            logger.log_info(f"{Icons.tick} Local voice output ENABLED")
        except Exception as exc:
            self._tts_worker = None
            self._tts_coalescer = None
            logger.log_error(f"{Icons.error} Local voice output unavailable: {exc}")

    def _refresh_tts_voice_catalog(self) -> None:
        """Refresh the runtime TTS voice catalogue without hiding failures."""
        try:
            rows = refresh_tts_voice_catalog(
                db_session=self.db_session,
                config_mgr=self.config_mgr,
                orac_home=APP_HOME,
            )
            logger.log_info(
                f"{Icons.tick} TTS voice catalogue refreshed: {len(rows)} voice(s)"
            )
        except Exception as exc:
            _log_exception("TTS voice catalogue refresh failed", exc)

    def _create_tts_coalescer(self) -> TtsChunkCoalescer:
        """Create the local TTS chunk coalescer from configuration."""
        enabled = self.config_mgr.bool_config_value(
            "voice",
            "tts_coalesce_enabled",
            default=True,
        )
        max_chars = self.config_mgr.int_config_value(
            "voice",
            "tts_coalesce_max_chars",
            default=DEFAULT_TTS_COALESCE_MAX_CHARS,
        )
        min_chunks = self.config_mgr.int_config_value(
            "voice",
            "tts_coalesce_min_chunks",
            default=DEFAULT_TTS_COALESCE_MIN_CHUNKS,
        )
        logger.log_info(
            f"{Icons.info} TTS coalescing enabled={enabled} "
            f"max_chars={max_chars} min_chunks={min_chunks}"
        )
        return TtsChunkCoalescer(
            enabled=enabled,
            max_chars=max_chars,
            min_chunks=min_chunks,
        )

    def _handle_voice_event(self, event: VoiceEvent) -> None:
        """Log a safe summary of local voice worker events."""
        if event.event_type == "VoiceError":
            logger.log_warning(f"{Icons.warn} Voice error: {event.to_dict()}")
            self._publish_voice_playback_event(event)
            return
        logger.log_debug(f"Voice event: {event.to_dict()}")
        self._publish_voice_playback_event(event)

    @staticmethod
    def _voice_subscription_key(
        *,
        session_id: str,
        turn_id: str,
    ) -> tuple[str, str]:
        """Return the subscriber map key for a voice session turn."""
        return (str(session_id or ""), str(turn_id or ""))

    def _register_voice_event_subscriber(
        self,
        *,
        session_id: str,
        turn_id: str,
        subscription: _VoicePlaybackSubscription,
    ) -> None:
        """Register a stream subscriber for playback lifecycle events."""
        if not hasattr(self, "_voice_event_subscriber_lock"):
            self._voice_event_subscriber_lock = threading.Lock()
        if not hasattr(self, "_voice_event_subscribers"):
            self._voice_event_subscribers = {}
        key = self._voice_subscription_key(
            session_id=session_id,
            turn_id=turn_id,
        )
        if not key[0] or not key[1]:
            return
        with self._voice_event_subscriber_lock:
            self._voice_event_subscribers.setdefault(key, []).append(subscription)

    def _unregister_voice_event_subscriber(
        self,
        *,
        session_id: str,
        turn_id: str,
        subscription: _VoicePlaybackSubscription,
    ) -> None:
        """Unregister a playback lifecycle event subscriber."""
        if not hasattr(self, "_voice_event_subscriber_lock"):
            self._voice_event_subscriber_lock = threading.Lock()
        if not hasattr(self, "_voice_event_subscribers"):
            self._voice_event_subscribers = {}
        key = self._voice_subscription_key(
            session_id=session_id,
            turn_id=turn_id,
        )
        with self._voice_event_subscriber_lock:
            subscriptions = self._voice_event_subscribers.get(key)
            if not subscriptions:
                return
            self._voice_event_subscribers[key] = [
                item for item in subscriptions if item is not subscription
            ]
            if not self._voice_event_subscribers[key]:
                self._voice_event_subscribers.pop(key, None)

    def _mark_voice_playback_expected(
        self,
        *,
        session_id: str,
        turn_id: str,
    ) -> None:
        """Mark that a voice turn has queued audio expected to play."""
        if not hasattr(self, "_voice_event_subscriber_lock"):
            self._voice_event_subscriber_lock = threading.Lock()
        if not hasattr(self, "_voice_event_subscribers"):
            self._voice_event_subscribers = {}
        key = self._voice_subscription_key(
            session_id=session_id,
            turn_id=turn_id,
        )
        with self._voice_event_subscriber_lock:
            for subscription in self._voice_event_subscribers.get(key, []):
                subscription.playback_expected = True

    def _mark_voice_playback_queued(
        self,
        *,
        session_id: str,
        turn_id: str,
    ) -> None:
        """Mark that one more utterance has been queued for playback."""
        if not hasattr(self, "_voice_event_subscriber_lock"):
            self._voice_event_subscriber_lock = threading.Lock()
        if not hasattr(self, "_voice_event_subscribers"):
            self._voice_event_subscribers = {}
        key = self._voice_subscription_key(
            session_id=session_id,
            turn_id=turn_id,
        )
        with self._voice_event_subscriber_lock:
            for subscription in self._voice_event_subscribers.get(key, []):
                subscription.playback_expected = True
                subscription.playback_queued += 1

    def _build_voice_playback_event_frame(
        self,
        event: VoiceEvent,
        *,
        frame_type: str,
    ) -> dict[str, Any]:
        """Build a protocol frame for a TTS playback lifecycle event."""
        event_dict = event.to_dict()
        payload: dict[str, Any] = {
            "turn_id": event.turn_id,
            "request_id": event.turn_id,
            "timestamp": event_dict.get("created_on") or iso_now(),
        }
        utterance_id = str(event_dict.get("utterance_id") or "")
        if utterance_id:
            payload["utterance_id"] = utterance_id
            payload["chunk_id"] = utterance_id
        reason = str(
            event_dict.get("reason")
            or event_dict.get("message")
            or ""
        )
        if reason:
            payload["reason"] = reason
        frame = {
            "v": 1,
            "type": frame_type,
            "id": new_id("evt"),
            "reply_to": event.turn_id,
            "ts": iso_now(),
            "route": "orac.prompt",
            "meta": {
                "status": "error" if frame_type == "tts_playback_error" else "ok",
                "model": self.model_name,
                "req_id": event.turn_id,
            },
            "payload": payload,
            "error": None,
        }
        if frame_type == "tts_playback_error":
            frame["error"] = {
                "code": str(event_dict.get("code") or "TTS_PLAYBACK_ERROR"),
                "message": str(event_dict.get("message") or "TTS playback failed"),
            }
        self._validate_outbound_protocol_frame(
            frame,
            context="Voice playback event failed protocol validation",
        )
        return frame

    def _publish_voice_playback_event(self, event: VoiceEvent) -> None:
        """Publish TTS playback lifecycle events to active stream clients."""
        if not hasattr(self, "_voice_event_subscriber_lock"):
            self._voice_event_subscriber_lock = threading.Lock()
        if not hasattr(self, "_voice_event_subscribers"):
            self._voice_event_subscribers = {}
        event_type_map = {
            "VoiceTtsPlaybackStarted": "tts_playback_started",
            "VoiceTtsPlaybackFinished": "tts_playback_finished",
            "VoiceTtsPlaybackCancelled": "tts_playback_cancelled",
            "VoiceTtsPlaybackError": "tts_playback_error",
            "VoiceTurnCancelled": "tts_playback_cancelled",
            "VoiceTurnComplete": "voice_turn_complete",
            "VoiceError": "tts_playback_error",
        }
        frame_type = event_type_map.get(event.event_type)
        if frame_type is None:
            return

        key = self._voice_subscription_key(
            session_id=event.session_id,
            turn_id=event.turn_id,
        )
        with self._voice_event_subscriber_lock:
            subscriptions = list(self._voice_event_subscribers.get(key, []))
        if not subscriptions:
            return

        frame = self._build_voice_playback_event_frame(
            event,
            frame_type=frame_type,
        )
        for subscription in subscriptions:
            subscription.callback(frame)

    def _route_stream_event_to_voice(
        self,
        req_env: dict,
        event_type: str,
        payload: dict[str, Any] | None,
    ) -> None:
        """Queue speech for stream text chunks, coalescing TTS only."""
        worker = getattr(self, "_tts_worker", None)
        if worker is None:
            return

        event_payload = payload if isinstance(payload, dict) else {}
        session_id = str(
            event_payload.get("voice_session_id")
            or (req_env.get("meta") or {}).get("session_id")
            or event_payload.get("session_id")
            or "unknown-session"
        )
        turn_id = str(
            event_payload.get("turn_id")
            or req_env.get("id")
            or "unknown-turn"
        )
        coalescer = getattr(self, "_tts_coalescer", None)
        request_meta = req_env.get("meta") if isinstance(req_env, dict) else {}
        tts_voice = (
            request_meta.get("tts_voice")
            if isinstance(request_meta, dict)
            and isinstance(request_meta.get("tts_voice"), dict)
            else None
        )

        if event_type == "text_chunk":
            chunk_text = str(event_payload.get("chunk") or "").strip()
            if not chunk_text:
                return
            if coalescer is None:
                queued = worker.enqueue_text(
                    session_id=session_id,
                    turn_id=turn_id,
                    text=chunk_text,
                    tts_voice=tts_voice,
                )
                if queued:
                    self._mark_voice_playback_queued(
                        session_id=session_id,
                        turn_id=turn_id,
                    )
                    self._mark_voice_playback_expected(
                        session_id=session_id,
                        turn_id=turn_id,
                    )
                return
            for speech_text in coalescer.add_chunk(
                session_id=session_id,
                turn_id=turn_id,
                text=chunk_text,
            ):
                queued = worker.enqueue_text(
                    session_id=session_id,
                    turn_id=turn_id,
                    text=speech_text,
                    tts_voice=tts_voice,
                )
                if queued:
                    self._mark_voice_playback_queued(
                        session_id=session_id,
                        turn_id=turn_id,
                    )
                    self._mark_voice_playback_expected(
                        session_id=session_id,
                        turn_id=turn_id,
                    )
            return

        if event_type in {"stream_end", "stream_error", "stream_cancelled"}:
            terminal_texts: list[tuple[str, str]] = []
            if coalescer is not None:
                final_text = coalescer.flush(
                    session_id=session_id,
                    turn_id=turn_id,
                )
                if final_text:
                    terminal_texts.append((turn_id, final_text))
                if not final_text and "turn_id" not in event_payload:
                    terminal_texts.extend(
                        coalescer.flush_session(session_id=session_id)
                    )
                for terminal_turn_id, speech_text in terminal_texts:
                    queued = worker.enqueue_text(
                        session_id=session_id,
                        turn_id=terminal_turn_id,
                        text=speech_text,
                        tts_voice=tts_voice,
                    )
                    if queued:
                        self._mark_voice_playback_queued(
                            session_id=session_id,
                            turn_id=terminal_turn_id,
                        )
                        self._mark_voice_playback_expected(
                            session_id=session_id,
                            turn_id=terminal_turn_id,
                        )
            if worker is not None:
                mark_complete = getattr(worker, "mark_turn_input_complete", None)
                if callable(mark_complete):
                    completed_turn_ids = {
                        terminal_turn_id
                        for terminal_turn_id, _text in terminal_texts
                    } or {turn_id}
                    for completed_turn_id in completed_turn_ids:
                        mark_complete(
                            session_id=session_id,
                            turn_id=completed_turn_id,
                        )

    def cancel_voice_turn(self, *, session_id: str, turn_id: str) -> int:
        """Cancel local voice output for a client session turn."""
        worker = getattr(self, "_tts_worker", None)
        if worker is None:
            return 0
        coalescer = getattr(self, "_tts_coalescer", None)
        if coalescer is not None:
            coalescer.cancel_turn(session_id=session_id, turn_id=turn_id)
        return worker.cancel_turn(session_id=session_id, turn_id=turn_id)

    def cancel_voice_session(self, *, session_id: str) -> int:
        """Cancel local voice output for a client session."""
        worker = getattr(self, "_tts_worker", None)
        if worker is None:
            return 0
        coalescer = getattr(self, "_tts_coalescer", None)
        if coalescer is not None:
            coalescer.cancel_session(session_id=session_id)
        return worker.cancel_session(session_id=session_id)

    def cancel_active_voice_turn(self, *, session_id: str) -> int:
        """Cancel the active local voice turn for a client session."""
        worker = getattr(self, "_tts_worker", None)
        if worker is None:
            return 0
        return worker.cancel_active_turn(session_id=session_id)

    def cancel_all_voice(self) -> int:
        """Cancel all local voice output immediately."""
        worker = getattr(self, "_tts_worker", None)
        if worker is None:
            return 0
        coalescer = getattr(self, "_tts_coalescer", None)
        if coalescer is not None:
            coalescer.clear()
        return worker.cancel_all(reason="orac cancellation requested")

    def _mark_voice_turn_cancelled(
        self,
        *,
        session_id: str,
        turn_id: str,
    ) -> None:
        """Mark a streamed voice turn as cancelled by local barge-in."""
        if not session_id or not turn_id:
            return
        cancelled = getattr(self, "_voice_cancelled_turns", None)
        if cancelled is None:
            self._voice_cancelled_turns = set()
            cancelled = self._voice_cancelled_turns
        cancelled.add((session_id, turn_id))

    def _is_voice_turn_cancelled(
        self,
        *,
        session_id: str,
        turn_id: str,
    ) -> bool:
        """Return whether a streamed voice turn should stop emitting."""
        cancelled = getattr(self, "_voice_cancelled_turns", set())
        return (session_id, turn_id) in cancelled

    def _clear_voice_turn_cancelled(
        self,
        *,
        session_id: str,
        turn_id: str,
    ) -> None:
        """Clear cancellation state for a completed voice turn."""
        cancelled = getattr(self, "_voice_cancelled_turns", None)
        if cancelled is not None:
            cancelled.discard((session_id, turn_id))
        worker = getattr(self, "_tts_worker", None)
        clear_cancelled_turn = getattr(worker, "clear_cancelled_turn", None)
        if callable(clear_cancelled_turn):
            clear_cancelled_turn(session_id=session_id, turn_id=turn_id)

    def _handle_voice_cancel_request(self, req_env: dict) -> str:
        """Handle a local voice cancellation control request."""
        payload = req_env.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        session_id = str(payload.get("session_id") or "").strip()
        turn_id = str(payload.get("turn_id") or "").strip()
        scope = str(payload.get("scope") or "active").strip().lower()
        reason = str(payload.get("reason") or "voice cancellation")
        discarded = 0

        logger.log_info(
            f"{Icons.info} Voice cancellation requested: "
            f"session={session_id or '-'} turn={turn_id or '-'} "
            f"scope={scope} reason={reason}"
        )
        if scope == "turn" and session_id and turn_id:
            self._mark_voice_turn_cancelled(
                session_id=session_id,
                turn_id=turn_id,
            )
            discarded = self.cancel_voice_turn(
                session_id=session_id,
                turn_id=turn_id,
            )
        elif scope == "session" and session_id:
            discarded = self.cancel_voice_session(session_id=session_id)
        elif scope == "all":
            discarded = self.cancel_all_voice()
        elif session_id:
            discarded = self.cancel_active_voice_turn(session_id=session_id)

        resp = {
            "v": 1,
            "type": "response",
            "id": new_id("res"),
            "reply_to": req_env.get("id"),
            "ts": iso_now(),
            "route": "orac.voice.cancel",
            "meta": {
                "status": "ok",
                "model": self.model_name,
                "req_id": req_env.get("id"),
            },
            "payload": {
                "cancelled": bool(session_id or scope == "all"),
                "discarded": int(discarded),
            },
            "error": None,
        }
        try:
            validate_frame(resp)
        except Exception as e:
            _log_exception("Voice cancel response failed validation", e)
        return json.dumps(resp, ensure_ascii=False)

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
        retrieval_pack: GroundingPack | None = None,
    ) -> str:
        try:
            dump_prompt = self._should_dump_prompt()
            default_timezone = getattr(self, "_default_timezone", "Europe/London")
            prefs = {
                "timezone": meta.get("timezone") or default_timezone,
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
            retrieval_block = ""
            if retrieval_pack is not None and retrieval_pack.evidence_block:
                retrieval_block = (
                    f"{retrieval_pack.evidence_block}\n\n"
                )
            retrieval_response_style = normalize_retrieval_response_style(
                meta.get("retrieval_response_style")
                or getattr(self, "_retrieval_response_style", "normal")
            )
            retrieval_directive = ""
            if retrieval_pack is not None and retrieval_pack.evidence_block:
                retrieval_directive = build_retrieval_response_guidance(
                    response_style=retrieval_response_style,
                    retrieval_pack=retrieval_pack,
                )
                if retrieval_directive:
                    retrieval_directive = (
                        "The user explicitly requested internet retrieval, and Orac has already "
                        "retrieved web evidence above. "
                        f"{retrieval_directive}\n"
                    )

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
                    f"{retrieval_directive}"
                )
                preamble = (
                    f"{primer_inline}\n"
                    "Prior conversation is disabled for this reply; use only the new user message.\n\n"
                    f"{clock}\n\n"
                    f"{user_facts_block}"
                    f"{routing_block}"
                    f"{retrieval_block}"
                    "Current user message:\n"
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
                "Use the conversation context to resolve references, follow-up wording, and user-provided session facts. "
                "If the current message is a short or ambiguous follow-up, resolve it against the immediately "
                "preceding user/assistant exchange rather than an older unrelated topic. "
                "Do not mention, label, summarise, or quote the conversation context in the reply unless the user "
                "explicitly asks about Orac's prompt or context. "
                "For ordinary factual questions, use your general knowledge as well as relevant context. "
                "Do not treat earlier assistant answers as authoritative if they conflict with reliable knowledge; "
                "correct materially wrong earlier answers plainly. "
                "If a proper noun appears misspelled or variant, state the likely interpretation and answer under "
                "that interpretation; ask for clarification only when multiple plausible meanings remain. "
                "For personal/session facts, only claim facts present in authenticated context or recent exchange. "
                "Keep the reply concise.\n"
                f"{retrieval_directive}"
            )

            preamble = (
                    f"{primer_inline}\n"
                    "Use recent context only if relevant.\n\n"
                    f"{clock}\n\n"
                    f"{user_facts_block}"
                    f"{routing_block}"
                    f"{retrieval_block}"
                    "Recent conversation context:\n"
                    + ("\n".join(history_lines) if history_lines else "")
                    + "\n\nCurrent user message:\n"
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
            "Conversation context:\n"
            f"USER: Reply with the exact token `{probe_token}` and nothing else.\n"
            f"ASSISTANT: {probe_token}\n\n"
            "Current user message:\n"
            "What exact token did I ask you to repeat? Reply with the exact token only."
        )

        try:
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
        except Exception as exc:
            self._mark_llm_registry_probe_failed(
                db_session=db_session,
                llm_id=llm_id,
                existing_properties=properties,
                model_metadata=model_metadata,
                reason=str(exc),
            )
            logger.log_warning(
                f"{Icons.warn} LLM registry probe failed for row {llm_id}; "
                "marked as model-managed context."
            )
            return

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

    def _mark_llm_registry_probe_failed(
        self,
        *,
        db_session: DBSession,
        llm_id: Any,
        existing_properties: Any,
        model_metadata: dict[str, Any] | None,
        reason: str,
    ) -> None:
        """Persist a non-retryable failed probe result for one registry row."""
        merged_properties = self._build_llm_registry_probe_properties(
            existing_properties,
            history_probe_status="failed",
            supports_provider_history="N",
            suggested_context_policy="model",
            history_probe_checked_on=iso_now(),
            first_response_ms=None,
            second_response_ms=None,
            total_response_ms=None,
            responsiveness_class="failed",
            first_reply=None,
            second_reply=None,
            model_metadata=model_metadata,
        )
        parsed = json.loads(merged_properties)
        parsed["history_probe_error"] = reason[:500]
        merged_properties = json.dumps(
            parsed,
            ensure_ascii=False,
            default=_json_default,
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
            self.plugin_service_manager = PluginServiceManager(
                logger=logger,
                config_mgr=self.config_mgr,
            )
            self.plugin_audit_adapter = PluginAuditAdapter(
                db_session=self.db_session,
                logger=logger,
            )
            self.plugin_confirmation_broker = PluginConfirmationBroker()
            self.plugin_router = PluginRouter(
                plugin_manager=self.plugin_manager,
                logger=logger,
                config_mgr=self.config_mgr,
                context_manager=self.ctx,
                confirmation_broker=self.plugin_confirmation_broker,
            )
            self.plugin_execution_service = PluginExecutionService(
                plugin_router=self.plugin_router,
                logger=logger,
                plugin_audit_adapter=self.plugin_audit_adapter,
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
            self.plugin_execution_service = None
            self.plugin_audit_adapter = None
            self.plugin_confirmation_broker = None
            self.plugin_service_manager = None
            self._plugin_routing_ready = False
            _log_exception("Plugin routing initialisation failed (non-fatal)", e)

    def _init_retrieval(self) -> None:
        """Initialise explicit-only internet retrieval if configuration allows it."""
        try:
            searxng_base_url = self.config_mgr.config_value(
                "retrieval.searxng",
                "base_url",
                default="http://127.0.0.1:8080",
            )
            searxng_timeout_seconds = self.config_mgr.float_config_value(
                "retrieval.searxng",
                "timeout_seconds",
                default=5.0,
            )
            max_response_bytes = self.config_mgr.int_config_value(
                "retrieval",
                "max_response_bytes",
                default=256_000,
            )
            max_redirects = self.config_mgr.int_config_value(
                "retrieval",
                "max_redirects",
                default=3,
            )
            search_provider = SearXNGSearchProvider(
                base_url=searxng_base_url,
                timeout_seconds=searxng_timeout_seconds,
                logger=logger,
            )
            broker = SearchBroker(
                logger=logger,
                config_mgr=self.config_mgr,
                providers={"searxng": search_provider},
            )
            source_fetcher = SourceFetcher(
                logger=logger,
                timeout_seconds=searxng_timeout_seconds,
                max_sources_to_fetch=broker.max_sources_to_fetch,
                max_bytes=max_response_bytes,
                max_redirects=max_redirects,
            )
            grounding_pack_builder = GroundingPackBuilder()
            self.retrieval_service = ExplicitRetrievalService(
                search_broker=broker,
                source_fetcher=source_fetcher,
                grounding_pack_builder=grounding_pack_builder,
                logger=logger,
            )
            self.retrieval_decision_service = RetrievalDecisionService(
                settings=broker.settings,
                logger=logger,
            )
            logger.log_info(
                f"{Icons.info} Explicit retrieval subsystem initialised with provider "
                f"'{broker.settings.default_search_provider}'."
            )
        except Exception as e:
            self.retrieval_service = None
            self.retrieval_decision_service = None
            _log_exception("Explicit retrieval initialisation failed (non-fatal)", e)

    def refresh_plugin_routing(self) -> dict[str, Any] | None:
        """Bootstraps or refreshes plugin routing state on demand."""
        if not self._plugin_routing_enabled or self.plugin_manager is None:
            logger.log_info(f"{Icons.info} Plugin routing refresh skipped because subsystem is unavailable.")
            return None
        logger.log_info(f"{Icons.info} Plugin routing refresh requested.")
        report = self.plugin_manager.refresh()
        service_status = self._refresh_plugin_services_from_discovery()
        if service_status is not None:
            report["service_lifecycle"] = service_status
        self._plugin_routing_ready = True
        logger.log_info(
            f"{Icons.info} Plugin routing refresh complete: "
            f"discovered={report.get('discovered', 0)} "
            f"enabled={report.get('enabled', 0)} "
            f"cache_hits={report.get('cache_hits', 0)} "
            f"re_embedded={report.get('re_embedded', 0)}"
        )
        return report

    def _refresh_plugin_services_from_discovery(self) -> dict[str, Any] | None:
        """Register and auto-start service-capable plugins from the latest discovery."""
        service_manager = getattr(self, "plugin_service_manager", None)
        plugin_manager = getattr(self, "plugin_manager", None)
        if service_manager is None or plugin_manager is None:
            logger.log_debug("Plugin service lifecycle unavailable; skipping service refresh.")
            return None

        discovered_manifests = getattr(plugin_manager, "discovered_manifests", None)
        manifests = (
            list(discovered_manifests())
            if callable(discovered_manifests)
            else []
        )
        service_manifests = [
            manifest
            for manifest in manifests
            if manifest.runtime_mode in {"service", "hybrid"}
        ]
        if service_manager.service_ids():
            logger.log_info(f"{Icons.info} Plugin service refresh stopping previously managed services.")
            service_manager.stop_all()

        registration_status = service_manager.register_manifests(service_manifests)
        service_manager.start_auto_services()
        status = service_manager.status()
        logger.log_info(
            f"{Icons.info} Plugin service refresh complete: "
            f"registered={status.get('registered', 0)} "
            f"dependency_invalid={status.get('dependency_invalid', 0)}"
        )
        return status or registration_status

    def shutdown_plugin_services(self) -> None:
        """Stop all supervised plugin services owned by this Orac instance."""
        service_manager = getattr(self, "plugin_service_manager", None)
        if service_manager is None:
            return
        try:
            logger.log_info(f"{Icons.info} Plugin service shutdown requested.")
            service_manager.stop_all()
        except Exception as exc:
            _log_exception("Plugin service shutdown failed", exc)

    def shutdown(self) -> None:
        """Shut down runtime resources owned directly by this Orac instance."""
        self.shutdown_plugin_services()

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

    def _execute_plugin_request(
        self,
        *,
        prompt: str,
        meta: dict[str, Any],
        plugin_routing_handoff: PluginRoutingHandoff | None,
        auth_user: str,
        request_context: dict[str, Any] | None = None,
    ) -> Any | None:
        """Delegate plugin execution through the plugin execution service."""
        plugin_execution_service = getattr(self, "plugin_execution_service", None)
        if plugin_execution_service is None:
            plugin_router = getattr(self, "plugin_router", None)
            if plugin_router is None:
                return None
            plugin_execution_service = PluginExecutionService(
                plugin_router=plugin_router,
                logger=logger,
                plugin_audit_adapter=getattr(self, "plugin_audit_adapter", None),
            )
            self.plugin_execution_service = plugin_execution_service
        return plugin_execution_service.execute(
            prompt=prompt,
            meta=meta,
            handoff=plugin_routing_handoff,
            auth_user=auth_user,
            request_context=request_context,
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
            tts_voice_pref = self.ctx.get_user_preference_value(
                username=auth_user,
                pref_key="tts_voice",
            )
        except Exception as e:
            _log_exception("Failed to load tts_voice preference", e)
            tts_voice_pref = None

        tts_voice_selection_checked = False
        try:
            tts_voice = resolve_tts_voice_selection(
                db_session=self.db_session,
                config_mgr=self.config_mgr,
                preferred_voice_key=(
                    str(tts_voice_pref).strip()
                    if tts_voice_pref not in (None, "")
                    else None
                ),
                username=auth_user,
            )
            tts_voice_selection_checked = True
        except Exception as e:
            _log_exception("Failed to resolve selected TTS voice", e)
            tts_voice = None

        if tts_voice is not None:
            enriched_meta["tts_voice_key"] = tts_voice.tts_voice_key
            enriched_meta["tts_voice"] = tts_voice.to_runtime_dict()
        elif tts_voice_selection_checked:
            enriched_meta["tts_voice"] = {
                "tts_voice_key": "__unavailable__",
                "provider_code": "unavailable",
                "provider_voice_id": "",
            }

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
        else:
            enriched_meta["personality_code"] = personality_code or "DEFAULT"

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

    def _load_model_generation_preset(
        self,
        *,
        model_preset_id: Any = None,
        model_preset_code: Any = None,
    ) -> dict[str, Any]:
        """Load an active model generation preset from the context layer."""
        try:
            return self.ctx.get_model_generation_preset(
                model_preset_id=model_preset_id,
                model_preset_code=(
                    str(model_preset_code).strip().upper()
                    if model_preset_code not in (None, "")
                    else None
                ),
            )
        except Exception as e:
            _log_exception("Failed to load model generation preset", e)
            return {}

    def _resolve_generation_options(
        self,
        *,
        meta: dict[str, Any],
        provider: str,
    ) -> dict[str, Any]:
        """Resolve provider-neutral generation options for one request.

        Personas reference a default preset, but do not own raw generation
        fields. A request-supplied preset is treated as a selected/default
        preset underneath the persona default. Provider adapters omit
        unsupported fields.
        """
        del provider
        resolved = dict(SYSTEM_GENERATION_DEFAULTS)
        request_meta = meta if isinstance(meta, dict) else {}
        personality = request_meta.get("orac_personality")
        personality = personality if isinstance(personality, dict) else {}

        selected_preset = {}
        if request_meta.get("model_preset_id") not in (None, ""):
            selected_preset = self._load_model_generation_preset(
                model_preset_id=request_meta.get("model_preset_id"),
            )
        elif request_meta.get("model_preset_code") not in (None, ""):
            selected_preset = self._load_model_generation_preset(
                model_preset_code=request_meta.get("model_preset_code"),
            )
        resolved.update(_generation_options_from_preset(selected_preset))

        persona_preset = {}
        if personality.get("MODEL_PRESET_ID") not in (None, ""):
            persona_preset = self._load_model_generation_preset(
                model_preset_id=personality.get("MODEL_PRESET_ID"),
            )
        resolved.update(_generation_options_from_preset(persona_preset))

        override = request_meta.get("generation_options_override")
        if (
            _as_bool(request_meta.get("admin_debug_generation_override")) is True
            and isinstance(override, dict)
        ):
            for key in GENERATION_PRESET_FIELDS:
                option_key = key.lower()
                if option_key in override:
                    resolved[option_key] = override[option_key]

        return resolved

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

        provider_registry = getattr(self, "provider_registry", None)
        if provider_registry is None:
            provider_registry = ProviderRegistry(logger=logger)
            self.provider_registry = provider_registry
        try:
            connector = provider_registry.create_connector(
                provider_id=key[0],
                service_url=key[1],
                model_name=key[2],
            )
        except ValueError as exc:
            raise RuntimeError(f"Unsupported LLM service: {service_id}") from exc
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
        provider_registry = getattr(self, "provider_registry", None)
        if provider_registry is None:
            provider_registry = ProviderRegistry(logger=logger)
            self.provider_registry = provider_registry
        return provider_registry.backend_model_available(
            active_provider_id=self.llm_service_id,
            provider_id=provider,
            model_name=model_name,
            available_models=self._available_backend_models,
            configured_model_name=self.model_name,
        )

    def _configured_model_lookup_candidates(self) -> list[str]:
        """Return model-name candidates for resolving the configured fallback row."""
        configured_model = str(self.model_name or "").strip()
        if not configured_model:
            return []

        provider_registry = getattr(self, "provider_registry", None)
        if provider_registry is None:
            provider_registry = ProviderRegistry(logger=logger)
            self.provider_registry = provider_registry
        return provider_registry.model_lookup_candidates(
            provider_id=self.llm_service_id,
            model_name=configured_model,
        )

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
        source: str = "configured_fallback",
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
            "source": source,
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
            return self._configured_fallback_selection(source="configured_default")

        llm_row = self.ctx.get_llm_registry_entry(preferred_llm_id)
        if not llm_row:
            return self._configured_fallback_selection(
                source="configured_fallback",
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
                source="configured_fallback",
                warning_message=(
                    f"{Icons.warn} User '{auth_user}' selected disabled LLM "
                    f"'{model_name}' (llm_id={llm_row.get('LLM_ID')}). "
                    f"Falling back to configured model '{self.model_name}'."
                )
            )

        if not self._backend_model_available(provider=provider, model_name=model_name):
            return self._configured_fallback_selection(
                source="configured_fallback",
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
        if created_new_conversation:
            return dict(new_conversation_selection)
        if stored_llm_id is None:
            return self._configured_fallback_selection(source="configured_default")

        llm_row = self.ctx.get_llm_registry_entry(stored_llm_id)
        if not llm_row:
            return self._configured_fallback_selection(
                source="configured_fallback",
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
                source="configured_fallback",
                warning_message=(
                    f"{Icons.warn} Conversation '{session_id}' for user '{auth_user}' "
                    f"references disabled LLM '{model_name}' (llm_id={stored_llm_id}). "
                    f"Using configured model '{self.model_name}' at runtime."
                )
            )

        if not self._backend_model_available(provider=provider, model_name=model_name):
            return self._configured_fallback_selection(
                source="configured_fallback",
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
        provider_registry = getattr(self, "provider_registry", None)
        if provider_registry is None:
            provider_registry = ProviderRegistry(logger=logger)
            self.provider_registry = provider_registry
        provider_registry.validate_or_prepare_model(
            provider_id=self.llm_service_id,
            service_url=self.service_url,
            model_name=self.model_name,
        )

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
        provenance: dict[str, Any] | None = None,
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
        if provenance:
            asst_meta["provenance"] = provenance
            asst_meta["source"] = provenance.get("source", "plugin_execution")
            asst_meta["plugin_id"] = provenance.get("plugin_id")
            asst_meta["plugin_status"] = provenance.get("status")
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

    def _remember_retrieval_context(
        self,
        session_id: str,
        *,
        user_message: str,
        previous_context: RetrievalTurnContext | None,
        retrieval_decision: Any | None,
        retrieval_outcome: RetrievalOutcome | None,
        retrieval_pack: GroundingPack | None,
        retrieval_status_override: str | None = None,
    ) -> None:
        """Store the most recent retrieval context for follow-up turns."""
        if retrieval_decision is None:
            return

        status = retrieval_status_override or "no_grounding"
        source_count: int | None = None
        result_count: int | None = None
        if retrieval_outcome is not None:
            status = str(retrieval_outcome.status or "no_grounding")
            request = getattr(retrieval_outcome, "request", None)
            if request is not None:
                result_count = getattr(request, "max_results", None)
        if retrieval_pack is not None:
            source_count = len(getattr(retrieval_pack, "fetched_sources", ()) or ())
            result_count = len(getattr(retrieval_pack, "search_results", ()) or ())
            status = "success"
        topic = str(getattr(retrieval_decision, "search_query", None) or user_message or "").strip()
        context = RetrievalTurnContext(
            topic=topic,
            topic_signature=build_topic_signature(topic or user_message or ""),
            original_user_message=str(user_message or "").strip(),
            retrieval_status=status,
            source_count=source_count,
            result_count=result_count,
            current_news_related=bool(
                (previous_context.current_news_related if previous_context is not None else False)
                or str(getattr(retrieval_decision, "reason_code", "")).startswith("current_news")
                or str(getattr(retrieval_decision, "reason_code", "")).startswith("current_affairs")
                or str(getattr(retrieval_decision, "reason_code", "")).startswith("retrieval_follow_up")
            ),
            current_affairs_related=bool(
                (previous_context.current_affairs_related if previous_context is not None else False)
                or str(getattr(retrieval_decision, "reason_code", "")).startswith("current_affairs")
            ),
            explicit_request=bool(getattr(retrieval_decision, "explicit_request", False)),
            automatic_request=bool(
                not getattr(retrieval_decision, "explicit_request", False)
                and getattr(retrieval_decision, "should_retrieve", False)
            ),
        )
        self._retrieval_context_by_session[session_id] = context

    # --- Response builder -----------------------------------------------------
    def _runtime_response_meta(
        self,
        req_env: dict,
        *,
        model_name: str | None = None,
        llm_source: str | None = None,
        user_registration: str = "registered",
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build response metadata including current runtime identity."""
        request_meta = req_env.get("meta")
        request_meta = request_meta if isinstance(request_meta, dict) else {}
        personality = request_meta.get("orac_personality")
        personality = personality if isinstance(personality, dict) else {}
        personality_code = str(
            request_meta.get("personality_code")
            or personality.get("PERSONALITY_CODE")
            or ""
        ).strip().upper()
        personality_name = str(
            personality.get("PERSONALITY_NAME") or personality_code
        ).strip()

        response_meta: dict[str, Any] = {
            "status": "error" if error else "ok",
            "model": str(model_name or self.model_name),
            "req_id": req_env.get("id"),
            "user_registration": user_registration,
        }
        llm_source_value = str(
            llm_source or getattr(self, "_active_llm_source", "") or ""
        ).strip()
        if llm_source_value:
            response_meta["llm_source"] = llm_source_value
        if personality_code:
            response_meta["personality_code"] = personality_code
        if personality_name:
            response_meta["personality_name"] = personality_name
        return response_meta

    def _build_response(self, req_env: dict, content: str, *,
                        stop_reason: str = "stop",
                        prompt_tokens: int = 0,
                        completion_tokens: int = 0,
                        model_name: str | None = None,
                        llm_source: str | None = None,
                        user_registration: str = "registered",
                        provenance: dict[str, Any] | None = None) -> dict:
        """Build a protocol-compliant non-streaming response envelope."""
        response_model = str(model_name or self.model_name)
        response_meta = self._runtime_response_meta(
            req_env,
            model_name=response_model,
            llm_source=llm_source,
            user_registration=user_registration,
        )
        if provenance:
            response_meta["provenance"] = provenance
            response_meta["source"] = provenance.get("source", "plugin_execution")
        resp = {
            "v": 1,
            "type": "response",
            "id": new_id("res"),
            "reply_to": req_env.get("id"),
            "ts": iso_now(),
            "route": req_env.get("route", "orac.prompt"),
            "meta": response_meta,
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

    def _validate_outbound_protocol_frame(
        self,
        frame: dict[str, Any],
        *,
        context: str,
    ) -> None:
        """Validate an outbound protocol frame and fail closed on errors."""
        try:
            validate_frame(frame)
        except Exception as e:
            _log_exception(context, e)
            raise

    def _build_stream_event(
        self,
        req_env: dict,
        event_type: str,
        *,
        payload: dict[str, Any] | None = None,
        model_name: str | None = None,
        llm_source: str | None = None,
        user_registration: str = "registered",
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a streamed response event envelope.

        Stream events intentionally use the same NDJSON transport as normal
        responses. The final ``response`` frame remains the compatibility
        terminator for clients that still need a complete answer.
        """
        frame = {
            "v": 1,
            "type": event_type,
            "id": new_id("evt"),
            "reply_to": req_env.get("id"),
            "ts": iso_now(),
            "route": req_env.get("route", "orac.prompt"),
            "meta": self._runtime_response_meta(
                req_env,
                model_name=model_name,
                llm_source=llm_source,
                user_registration=user_registration,
                error=error,
            ),
            "payload": payload or {},
            "error": error,
        }
        self._validate_outbound_protocol_frame(
            frame,
            context="Stream event failed protocol validation",
        )
        return frame

    async def _emit_stream_event(
        self,
        event_sink: StreamEventSink | None,
        req_env: dict,
        event_type: str,
        *,
        payload: dict[str, Any] | None = None,
        model_name: str | None = None,
        llm_source: str | None = None,
        user_registration: str = "registered",
        error: dict[str, Any] | None = None,
    ) -> None:
        """Emit one stream event when a sink is available."""
        frame = self._build_stream_event(
            req_env,
            event_type,
            payload=payload,
            model_name=model_name,
            llm_source=llm_source,
            user_registration=user_registration,
            error=error,
        )
        self._route_stream_event_to_voice(req_env, event_type, payload)
        if event_sink is None:
            return
        await event_sink(frame)

    def _missing_stream_speech_suffix(
        self,
        *,
        content: str,
        speech_chunks: list[str],
    ) -> str | None:
        """Return final answer text not already routed to speech chunks."""
        final_text = content.strip()
        if not final_text:
            return None

        spoken_text = " ".join(
            chunk.strip() for chunk in speech_chunks if chunk.strip()
        ).strip()
        if not spoken_text:
            return final_text
        if final_text == spoken_text:
            return None
        if final_text.startswith(spoken_text):
            suffix = final_text[len(spoken_text):].strip()
            return suffix or None
        return None

    async def _emit_complete_text_as_stream(
        self,
        event_sink: StreamEventSink | None,
        req_env: dict,
        content: str,
        *,
        model_name: str,
        llm_source: str | None,
        user_registration: str,
        session_id: str | None = None,
        turn_id: str | None = None,
        stop_reason: str = "stop",
    ) -> None:
        """Emit a completed text response as stream-compatible events."""
        await self._emit_stream_event(
            event_sink,
            req_env,
            "stream_start",
            payload={
                "content_type": "text",
                "voice_session_id": session_id,
                "turn_id": turn_id or req_env.get("id"),
            },
            model_name=model_name,
            llm_source=llm_source,
            user_registration=user_registration,
        )
        if content:
            await self._emit_stream_event(
                event_sink,
                req_env,
                "text_delta",
                payload={"delta": content},
                model_name=model_name,
                llm_source=llm_source,
                user_registration=user_registration,
            )
            chunker = TextChunker()
            chunks = chunker.add_delta(content)
            remainder = chunker.flush()
            for chunk in chunks + ([remainder] if remainder else []):
                await self._emit_stream_event(
                    event_sink,
                    req_env,
                    "text_chunk",
                    payload={
                        "chunk": chunk,
                        "session_id": session_id,
                        "voice_session_id": (req_env.get("meta") or {}).get("session_id"),
                        "turn_id": turn_id or req_env.get("id"),
                    },
                    model_name=model_name,
                    llm_source=llm_source,
                    user_registration=user_registration,
                )
        await self._emit_stream_event(
            event_sink,
            req_env,
            "stream_end",
            payload={
                "stop_reason": stop_reason,
                "voice_session_id": session_id,
                "turn_id": turn_id or req_env.get("id"),
            },
            model_name=model_name,
            llm_source=llm_source,
            user_registration=user_registration,
        )

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
    async def handle_request_events(self, message: str) -> AsyncIterator[str]:
        """Yield NDJSON response frames for a request.

        Non-streaming requests yield exactly one final response frame.
        Streaming requests yield zero or more stream events followed by the
        same final response envelope used by the legacy path.
        """
        queue: asyncio.Queue[str] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        voice_session_id = ""
        voice_turn_id = ""
        voice_subscription: _VoicePlaybackSubscription | None = None

        try:
            req_preview = json.loads(message)
        except Exception:
            req_preview = {}
        if isinstance(req_preview, dict):
            meta = req_preview.get("meta") or {}
            if (
                req_preview.get("route") == "orac.prompt"
                and bool(meta.get("stream"))
            ):
                voice_session_id = str(meta.get("session_id") or "")
                voice_turn_id = str(req_preview.get("id") or "")

        async def event_sink(event: dict[str, Any]) -> None:
            await queue.put(json.dumps(event, ensure_ascii=False))

        turn_complete_event: dict[str, Any] | None = None

        def voice_event_sink(event: dict[str, Any]) -> None:
            def _enqueue() -> None:
                nonlocal voice_subscription
                nonlocal turn_complete_event
                if voice_subscription is not None:
                    frame_type = str(event.get("type") or "")
                    if frame_type == "tts_playback_started":
                        voice_subscription.playback_started = True
                    elif frame_type == "tts_playback_finished":
                        voice_subscription.playback_finished += 1
                    elif frame_type in {
                        "tts_playback_cancelled",
                        "tts_playback_error",
                    }:
                        voice_subscription.playback_terminal = True
                    elif frame_type == "voice_turn_complete":
                        voice_subscription.playback_terminal = True
                        if turn_complete_event is None:
                            turn_complete_event = event
                        return
                queue.put_nowait(json.dumps(event, ensure_ascii=False))

            loop.call_soon_threadsafe(_enqueue)

        def synthesise_voice_turn_complete() -> dict[str, Any]:
            """Build a fallback completion frame for a drained voice turn."""
            timestamp = iso_now()
            frame = {
                "v": 1,
                "type": "voice_turn_complete",
                "id": new_id("evt"),
                "reply_to": voice_turn_id,
                "ts": timestamp,
                "route": "orac.prompt",
                "meta": {
                    "status": "ok",
                    "model": self.model_name,
                    "req_id": voice_turn_id,
                },
                "payload": {
                    "turn_id": voice_turn_id,
                    "request_id": voice_turn_id,
                    "timestamp": timestamp,
                    "reason": "playback-drained",
                },
                "error": None,
            }
            self._validate_outbound_protocol_frame(
                frame,
                context="Synthesised voice turn completion failed protocol validation",
            )
            return frame

        if voice_session_id and voice_turn_id:
            voice_subscription = _VoicePlaybackSubscription(
                callback=voice_event_sink
            )
            self._register_voice_event_subscriber(
                session_id=voice_session_id,
                turn_id=voice_turn_id,
                subscription=voice_subscription,
            )

        response_task = asyncio.create_task(
            self.handle_request(message, event_sink=event_sink)
        )

        try:
            playback_wait_started_at: float | None = None
            playback_timeout_logged = False
            while True:
                playback_pending = (
                    voice_subscription is not None
                    and voice_subscription.playback_expected
                    and voice_subscription.playback_finished
                    < voice_subscription.playback_queued
                )
                if response_task.done() and playback_pending:
                    if playback_wait_started_at is None:
                        playback_wait_started_at = time.monotonic()
                    timeout_seconds = (
                        VOICE_PLAYBACK_FINISH_TIMEOUT_SECONDS
                        if voice_subscription.playback_started
                        else VOICE_PLAYBACK_START_TIMEOUT_SECONDS
                    )
                    if (
                        not playback_timeout_logged
                        and time.monotonic() - playback_wait_started_at > timeout_seconds
                    ):
                        logger.log_warning(
                            f"{Icons.warn} Timed out waiting for TTS playback "
                            f"event: session={voice_session_id} turn={voice_turn_id} "
                            f"started={voice_subscription.playback_started}"
                        )
                        playback_timeout_logged = True
                        voice_subscription.playback_terminal = True
                else:
                    playback_wait_started_at = None

                if response_task.done() and queue.empty() and not playback_pending:
                    if voice_subscription is None:
                        break
                    if turn_complete_event is None:
                        log_message = (
                            f"Synthesising missing voice turn completion: "
                            f"session={voice_session_id} turn={voice_turn_id} "
                            f"queued={voice_subscription.playback_queued} "
                            f"finished={voice_subscription.playback_finished}"
                        )
                        if voice_subscription.playback_expected:
                            logger.log_warning(f"{Icons.warn} {log_message}")
                        else:
                            logger.log_debug(log_message)
                        turn_complete_event = synthesise_voice_turn_complete()
                    break
                try:
                    yield await asyncio.wait_for(queue.get(), timeout=0.05)
                except asyncio.TimeoutError:
                    continue

            yield await response_task
            if turn_complete_event is not None:
                yield json.dumps(
                    turn_complete_event,
                    ensure_ascii=False,
                )
        finally:
            if voice_subscription is not None:
                self._unregister_voice_event_subscriber(
                    session_id=voice_session_id,
                    turn_id=voice_turn_id,
                    subscription=voice_subscription,
                )
            if not response_task.done():
                response_task.cancel()

    async def handle_request(
        self,
        message: str,
        event_sink: StreamEventSink | None = None,
    ) -> str:
        try:
            req_env = json.loads(message)  # strict JSON
        except Exception as e:
            _log_exception("Failed to parse request JSON", e)
            err_env = {
                "v": 1, "type": "response", "id": new_id("res"),
                "reply_to": None, "ts": iso_now(), "route": "orac.prompt",
                "meta": {
                    "status": "error",
                    "model": self.model_name,
                    "llm_source": getattr(self, "_active_llm_source", None),
                },
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
                    "meta": {
                        "status": "error",
                        "model": self.model_name,
                        "req_id": req_env.get("id"),
                        "llm_source": getattr(self, "_active_llm_source", None),
                    },
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
                    "meta": {
                        "status": "error",
                        "model": self.model_name,
                        "req_id": req_env.get("id"),
                        "llm_source": getattr(self, "_active_llm_source", None),
                    },
                    "payload": None,
                    "error": {"code": "INVALID_FRAME", "message": str(e)},
                }
                return json.dumps(err, ensure_ascii=False)

            if req_env.get("route") == "orac.voice.cancel":
                return self._handle_voice_cancel_request(req_env)

            if req_env.get("route") != "orac.prompt":
                raise ValueError("Unsupported request type/route")

            # --- Extract prompt & meta -----------------------------------------
            messages = (req_env.get("payload") or {}).get("messages") or []
            prompt = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), "").strip()
            meta = req_env.get("meta") or {}
            incoming_voice_session_id = str(meta.get("session_id") or "")
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
            stream_requested = bool(meta.get("stream")) and event_sink is not None

            try:
                self._ensure_db_session_ready()
            except Exception as e:
                _log_exception("Oracle session validation failed (non-fatal)", e)

            meta = self._apply_user_preference_meta(meta, auth_user)
            req_env["meta"] = meta

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
            logger.log_debug(f"{Icons.tick} derived session_id_base='{session_id_base}'")
            new_conversation_selection = self._resolve_new_conversation_llm(
                auth_user=auth_user,
                meta=meta,
            )
            force_new_conversation = (
                _as_bool(meta.get("force_new_conversation")) is True
            )
            current_primer = _orac_system_primer(
                {
                    "reply_language": meta.get(
                        "reply_language",
                        self._reply_language,
                    ),
                    "orac_personality": meta.get("orac_personality"),
                },
                self._system_prompt_policy,
            )
            current_primer_fingerprint = _system_prompt_fingerprint(current_primer)

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

            if force_new_conversation and not created_new_conversation:
                logger.log_info(
                    f"{Icons.info} force_new_conversation requested for "
                    f"session '{session_id}'. Starting a new conversation."
                )
                try:
                    if getattr(self, "_archive_on_rollover", False):
                        self.ctx.archive_conversation(session_id)
                        logger.log_info(
                            f"{Icons.box} Archived prior conversation: "
                            f"{session_id}"
                        )
                    elif getattr(self, "_close_on_rollover", True):
                        self.ctx.close_conversation(session_id)
                        logger.log_info(
                            f"{Icons.stop} Closed prior conversation: "
                            f"{session_id}"
                        )
                    else:
                        logger.log_debug(
                            f"{Icons.info} Prior conversation left 'open': "
                            f"{session_id}"
                        )
                except Exception as e_state:
                    _log_exception(
                        "Failed to transition prior conversation during "
                        "forced rollover",
                        e_state,
                    )

                session_id = new_session_id(session_id_base)
                self.ctx.ensure_conversation(
                    user_name=auth_user,
                    session_id=session_id,
                    llm_id=new_conversation_selection.get("llm_id"),
                )
                created_new_conversation = True

            selected_default_llm_id = new_conversation_selection.get("llm_id")
            if (
                not created_new_conversation
                and new_conversation_selection.get("source") == "user_preference"
                and selected_default_llm_id is not None
            ):
                try:
                    conversation_llm_id = self.ctx.get_conversation_llm_id(session_id)
                except Exception as e:
                    _log_exception(
                        "Failed to read conversation LLM for reuse check",
                        e,
                    )
                    conversation_llm_id = None

                if (
                    conversation_llm_id is not None
                    and _as_int(conversation_llm_id, -1)
                    != _as_int(selected_default_llm_id, -2)
                ):
                    logger.log_info(
                        f"{Icons.info} Default LLM change detected for session '{session_id}': "
                        f"stored={conversation_llm_id}, selected={selected_default_llm_id}. "
                        "Starting a new conversation."
                    )
                    try:
                        if getattr(self, "_archive_on_rollover", False):
                            self.ctx.archive_conversation(session_id)
                            logger.log_info(f"{Icons.box} Archived prior conversation: {session_id}")
                        elif getattr(self, "_close_on_rollover", True):
                            self.ctx.close_conversation(session_id)
                            logger.log_info(f"{Icons.stop} Closed prior conversation: {session_id}")
                        else:
                            logger.log_debug(f"{Icons.info} Prior conversation left 'open': {session_id}")
                    except Exception as e_state:
                        _log_exception(
                            "Failed to transition prior conversation during LLM rollover",
                            e_state,
                        )

                    session_id = new_session_id(session_id_base)
                    self.ctx.ensure_conversation(
                        user_name=auth_user,
                        session_id=session_id,
                        llm_id=selected_default_llm_id,
                    )
                    created_new_conversation = True

            selected_personality_code = str(
                meta.get("personality_code") or "DEFAULT"
            ).strip().upper()
            if (
                not created_new_conversation
                and self.ctx.last_turn_index(session_id) > 0
            ):
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

            if (
                not created_new_conversation
                and self.ctx.last_turn_index(session_id) > 0
            ):
                try:
                    conversation_prompt_fingerprint = (
                        self.ctx.get_conversation_prompt_policy_fingerprint(
                            session_id
                        )
                    )
                except Exception as e:
                    _log_exception(
                        "Failed to read conversation prompt policy "
                        "fingerprint for reuse check",
                        e,
                    )
                    conversation_prompt_fingerprint = current_primer_fingerprint

                if conversation_prompt_fingerprint != current_primer_fingerprint:
                    logger.log_info(
                        f"{Icons.info} System prompt policy change detected "
                        f"for session '{session_id}'. Starting a new "
                        "conversation."
                    )
                    try:
                        if getattr(self, "_archive_on_rollover", False):
                            self.ctx.archive_conversation(session_id)
                            logger.log_info(
                                f"{Icons.box} Archived prior conversation: "
                                f"{session_id}"
                            )
                        elif getattr(self, "_close_on_rollover", True):
                            self.ctx.close_conversation(session_id)
                            logger.log_info(
                                f"{Icons.stop} Closed prior conversation: "
                                f"{session_id}"
                            )
                        else:
                            logger.log_debug(
                                f"{Icons.info} Prior conversation left "
                                f"'open': {session_id}"
                            )
                    except Exception as e_state:
                        _log_exception(
                            "Failed to transition prior conversation during "
                            "prompt policy rollover",
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
            effective_llm_source = str(
                effective_llm.get("source") or "configured_default"
            ).strip() or "configured_default"
            self._active_llm_source = effective_llm_source
            logger.log_info(
                f"{Icons.info} Effective LLM for session '{session_id}': "
                f"model='{effective_model_name}', provider='{effective_llm.get('provider')}', "
                f"llm_id={effective_llm_id}, source='{effective_llm_source}'"
            )
            generation_options = self._resolve_generation_options(
                meta=meta,
                provider=str(effective_llm.get("provider") or self.llm_service_id),
            )

            # --- Ensure a system primer is stored once per conversation ---------
            try:
                if self.ctx.last_turn_index(session_id) == 0:
                    self.ctx.save_system_turn(
                        session_id,
                        auth_user,
                        current_primer,
                        meta={
                            "kind": "primer",
                            "ts": iso_now(),
                            "protocol_version": PROTOCOL_VERSION,
                            "prompt_policy_fingerprint": (
                                current_primer_fingerprint
                            ),
                            "personality_code": str(
                                meta.get("personality_code") or "DEFAULT"
                            ).strip().upper(),
                        },
                        llm_id=effective_llm_id,
                    )
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

            conversation_id = None
            user_id = None
            try:
                conversation_lookup = getattr(self.ctx, "_conversation_id", None)
                if callable(conversation_lookup):
                    conversation_id = conversation_lookup(session_id)
            except Exception:
                conversation_id = None
            try:
                user_lookup = getattr(self.ctx, "_find_user_id", None)
                if callable(user_lookup):
                    user_id = user_lookup(auth_user)
            except Exception:
                user_id = None

            retrieval_decision = None
            previous_retrieval_context = self._retrieval_context_by_session.get(session_id)
            decision_service = getattr(self, "retrieval_decision_service", None)
            if decision_service is not None:
                try:
                    decide = getattr(decision_service, "decide", None)
                    if callable(decide):
                        retrieval_decision = decide(
                            prompt,
                            previous_context=previous_retrieval_context,
                        )
                except Exception as e:
                    _log_exception("Retrieval decision failed (non-fatal)", e)
                    retrieval_decision = None
            else:
                explicit_search_request = detect_explicit_search_request(prompt)
                if explicit_search_request is not None:
                    retrieval_decision = SimpleNamespace(
                        should_retrieve=True,
                        retrieval_type="internet",
                        confidence="high",
                        reason_code="explicit_request",
                        user_visible_reason="I’ll check that online.",
                        explicit_request=True,
                        requires_user_confirmation=False,
                        search_query=explicit_search_request.query,
                    )

            retrieval_pack = None
            retrieval_outcome: RetrievalOutcome | None = None
            retrieval_event_loop = asyncio.get_running_loop()

            def emit_retrieval_event(
                event_type: str,
                payload: dict[str, Any] | None = None,
            ) -> None:
                """Schedule one retrieval lifecycle event from a worker thread."""
                if not stream_requested or event_sink is None:
                    return

                async def _emit() -> None:
                    await self._emit_stream_event(
                        event_sink,
                        req_env,
                        event_type,
                        payload=payload or {},
                        model_name=effective_model_name,
                        user_registration=(
                            "anonymous"
                            if request_flags["anonymous_user"]
                            else "registered"
                        ),
                    )

                try:
                    future = asyncio.run_coroutine_threadsafe(
                        _emit(),
                        retrieval_event_loop,
                    )

                    def _log_future_result(done: Any) -> None:
                        try:
                            done.result()
                        except Exception as exc:
                            _log_exception("Retrieval event dispatch failed (non-fatal)", exc)

                    future.add_done_callback(_log_future_result)
                except Exception as exc:
                    _log_exception("Failed scheduling retrieval event (non-fatal)", exc)

            if retrieval_decision is not None:
                if retrieval_decision.requires_user_confirmation and not retrieval_decision.should_retrieve:
                    if stream_requested:
                            await self._emit_stream_event(
                                event_sink,
                                req_env,
                                "retrieval_skipped",
                                payload={
                                    "mode": "internet",
                                    "reason": "confirmation_required",
                                },
                                model_name=effective_model_name,
                                user_registration=(
                                    "anonymous"
                                if request_flags["anonymous_user"]
                                else "registered"
                            ),
                        )
                    content = retrieval_decision.user_visible_reason or "That may have changed recently; I should check online."
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
                        stop_reason="stop",
                        prompt_tokens=0,
                        completion_tokens=0,
                        model_name=effective_model_name,
                        user_registration=(
                            "anonymous" if request_flags["anonymous_user"] else "registered"
                        ),
                    )
                    if stream_requested:
                        await self._emit_complete_text_as_stream(
                            event_sink,
                            req_env,
                            content,
                            model_name=effective_model_name,
                            llm_source=effective_llm_source,
                            user_registration=(
                                "anonymous"
                                if request_flags["anonymous_user"]
                                else "registered"
                            ),
                            session_id=session_id,
                            turn_id=str(req_env.get("id") or ""),
                            stop_reason="stop",
                        )
                    return json.dumps(resp_env, ensure_ascii=False)

                if (
                    retrieval_decision.reason_code == "disabled"
                    and not retrieval_decision.should_retrieve
                ):
                    if stream_requested:
                        await self._emit_stream_event(
                            event_sink,
                            req_env,
                            "retrieval_skipped",
                            payload={
                                "mode": "internet",
                                "reason": "retrieval_disabled",
                            },
                            model_name=effective_model_name,
                            user_registration=(
                                "anonymous"
                                if request_flags["anonymous_user"]
                                else "registered"
                            ),
                        )
                    content = retrieval_decision.user_visible_reason or "I could not retrieve online evidence for that request."
                    self._remember_retrieval_context(
                        session_id,
                        user_message=prompt,
                        previous_context=previous_retrieval_context,
                        retrieval_decision=retrieval_decision,
                        retrieval_outcome=None,
                        retrieval_pack=None,
                        retrieval_status_override="disabled",
                    )
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
                        stop_reason="stop",
                        prompt_tokens=0,
                        completion_tokens=0,
                        model_name=effective_model_name,
                        user_registration=(
                            "anonymous" if request_flags["anonymous_user"] else "registered"
                        ),
                    )
                    if stream_requested:
                        await self._emit_complete_text_as_stream(
                            event_sink,
                            req_env,
                            content,
                            model_name=effective_model_name,
                            llm_source=effective_llm_source,
                            user_registration=(
                                "anonymous"
                                if request_flags["anonymous_user"]
                                else "registered"
                            ),
                            session_id=session_id,
                            turn_id=str(req_env.get("id") or ""),
                            stop_reason="stop",
                        )
                    return json.dumps(resp_env, ensure_ascii=False)

                if retrieval_decision.should_retrieve:
                    try:
                        retrieval_service = getattr(self, "retrieval_service", None)
                        if retrieval_service is not None:
                            if stream_requested:
                                await self._emit_stream_event(
                                    event_sink,
                                    req_env,
                                    "retrieval_start",
                                    payload={
                                        "mode": "internet",
                                        "reason": str(
                                            retrieval_decision.reason_code or "retrieval_request"
                                        ),
                                    },
                                    model_name=effective_model_name,
                                    user_registration=(
                                        "anonymous"
                                        if request_flags["anonymous_user"]
                                        else "registered"
                                    ),
                                )
                                await self._emit_stream_event(
                                    event_sink,
                                    req_env,
                                    "retrieval_query",
                                    payload={
                                        "query": str(
                                            retrieval_decision.search_query or prompt
                                        ),
                                        "provider": str(
                                            getattr(
                                                retrieval_service,
                                                "default_search_provider",
                                                "searxng",
                                            )
                                            or "searxng"
                                        ),
                                    },
                                    model_name=effective_model_name,
                                    user_registration=(
                                        "anonymous"
                                        if request_flags["anonymous_user"]
                                        else "registered"
                                    ),
                                )
                            if retrieval_decision.explicit_request:
                                build_outcome = getattr(
                                    retrieval_service,
                                    "build_grounding_outcome",
                                    None,
                                )
                                if callable(build_outcome):
                                    retrieval_outcome = await asyncio.to_thread(
                                        build_outcome,
                                        prompt,
                                        event_emitter=emit_retrieval_event,
                                    )
                                    retrieval_pack = retrieval_outcome.grounding_pack
                                else:
                                    retrieval_pack = retrieval_service.build_grounding_pack(prompt)
                            else:
                                build_outcome = getattr(
                                    retrieval_service,
                                    "build_grounding_outcome_for_request",
                                    None,
                                )
                                if callable(build_outcome):
                                    retrieval_request = SearchRequest(
                                        query=str(retrieval_decision.search_query or prompt),
                                        trigger_phrase=retrieval_decision.reason_code,
                                    )
                                    retrieval_outcome = await asyncio.to_thread(
                                        build_outcome,
                                        retrieval_request,
                                        event_emitter=emit_retrieval_event,
                                    )
                                    retrieval_pack = retrieval_outcome.grounding_pack
                                else:
                                    retrieval_outcome = RetrievalOutcome(
                                        requested=True,
                                        status="failed",
                                        message="I could not retrieve online evidence for that request.",
                                    )
                        elif stream_requested:
                                await self._emit_stream_event(
                                    event_sink,
                                    req_env,
                                    "retrieval_failed",
                                    payload={
                                        "mode": "internet",
                                        "reason": "service_unavailable",
                                    },
                                    model_name=effective_model_name,
                                    user_registration=(
                                        "anonymous"
                                    if request_flags["anonymous_user"]
                                    else "registered"
                                ),
                            )
                    except Exception as e:
                        _log_exception("Retrieval failed (non-fatal)", e)
                        retrieval_pack = None

                    if retrieval_pack is None:
                        content = (
                            retrieval_outcome.message
                            if retrieval_outcome is not None
                            else (
                                retrieval_decision.user_visible_reason
                                if retrieval_decision.explicit_request and retrieval_decision.reason_code == "disabled"
                                else "I could not retrieve online evidence for that request."
                            )
                        )
                        self._remember_retrieval_context(
                            session_id,
                            user_message=prompt,
                            previous_context=previous_retrieval_context,
                            retrieval_decision=retrieval_decision,
                            retrieval_outcome=retrieval_outcome,
                            retrieval_pack=None,
                        )
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
                            stop_reason="stop",
                            prompt_tokens=0,
                            completion_tokens=0,
                            model_name=effective_model_name,
                            user_registration=(
                                "anonymous" if request_flags["anonymous_user"] else "registered"
                            ),
                        )
                        if stream_requested:
                            await self._emit_complete_text_as_stream(
                                event_sink,
                                req_env,
                                content,
                                model_name=effective_model_name,
                                llm_source=effective_llm_source,
                                user_registration=(
                                    "anonymous"
                                    if request_flags["anonymous_user"]
                                    else "registered"
                                ),
                                session_id=session_id,
                                turn_id=str(req_env.get("id") or ""),
                                stop_reason="stop",
                            )
                        return json.dumps(resp_env, ensure_ascii=False)

            plugin_routing_handoff = None
            plugin_execution_result = None
            if retrieval_decision is None or not retrieval_decision.should_retrieve:
                plugin_routing_handoff = self._collect_plugin_routing_handoff(prompt, meta)
                plugin_execution_result = self._execute_plugin_request(
                    prompt=prompt,
                    meta=meta,
                    plugin_routing_handoff=plugin_routing_handoff,
                    auth_user=auth_user,
                    request_context={
                        "request_id": req_env.get("id"),
                        "correlation_id": req_env.get("meta", {}).get("correlation_id") if isinstance(req_env.get("meta"), dict) else None,
                        "turn_id": req_env.get("id"),
                        "session_id": session_id,
                        "conversation_id": conversation_id,
                        "message_id": None,
                        "user_id": user_id,
                    },
                )

            if plugin_execution_result is not None and plugin_execution_result.handled:
                content = plugin_execution_result.content
                plugin_provenance = plugin_execution_result.provenance
                last_ti = self._save_assistant_turn(
                    session_id,
                    auth_user,
                    content,
                    client=client,
                    req_id=req_env.get("id"),
                    show_reasoning=show_reasoning,
                    llm_id=effective_llm_id,
                    provenance=plugin_provenance,
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
                    provenance=plugin_provenance,
                )
                if stream_requested:
                    await self._emit_complete_text_as_stream(
                        event_sink,
                        req_env,
                        content,
                        model_name=effective_model_name,
                        llm_source=effective_llm_source,
                        user_registration=(
                            "anonymous"
                            if request_flags["anonymous_user"]
                            else "registered"
                        ),
                        session_id=session_id,
                        turn_id=str(req_env.get("id") or ""),
                        stop_reason=plugin_execution_result.stop_reason,
                    )
                return json.dumps(resp_env, ensure_ascii=False)

            # --- Build context-primed prompt -----------------------------------
            final_prompt = self._build_contextual_prompt(
                session_id,
                prompt,
                meta,
                auth_user,
                plugin_routing_handoff=plugin_routing_handoff,
                retrieval_pack=retrieval_pack,
            )
            short = (final_prompt[:1200] + " …") if len(final_prompt) > 1200 else final_prompt
            logger.log_info(f"{Icons.info} Final prompt (truncated): {short}")
            if self.enable_prompt_dump:
                _dump_debug_blob("final-prompt", final_prompt)

            prompt_tokens = 0
            completion_tokens = 0
            total_tokens = 0
            tokens_used: int | None = None
            stream_emitted_delta = False
            stream_cancelled = False
            voice_session_id = incoming_voice_session_id
            voice_turn_id = str(req_env.get("id") or "")

            if stream_requested:
                await self._emit_stream_event(
                    event_sink,
                    req_env,
                    "stream_start",
                    payload={
                        "content_type": "text",
                        "voice_session_id": voice_session_id,
                        "turn_id": voice_turn_id,
                    },
                    model_name=effective_model_name,
                    user_registration=(
                        "anonymous" if request_flags["anonymous_user"] else "registered"
                    ),
                )
                chunker = TextChunker()
                raw_parts: list[str] = []
                speech_chunks: list[str] = []
                stream_usage: LLMUsageMetadata | None = None

                def _capture_stream_usage(usage: LLMUsageMetadata) -> None:
                    """Capture final token metadata from a completed stream."""
                    nonlocal stream_usage
                    stream_usage = usage

                try:
                    for delta in llm_connector.stream_prompt_deltas(
                        prompt_type="U",
                        prompt=final_prompt,
                        generation_options=generation_options,
                        on_usage_metadata=_capture_stream_usage,
                    ):
                        if self._is_voice_turn_cancelled(
                            session_id=voice_session_id,
                            turn_id=voice_turn_id,
                        ):
                            stream_cancelled = True
                            logger.log_info(
                                f"{Icons.info} Stopping LLM stream consumption "
                                f"after voice interruption: session={voice_session_id} "
                                f"turn={voice_turn_id}"
                            )
                            await self._emit_stream_event(
                                event_sink,
                                req_env,
                                "stream_cancelled",
                                payload={
                                    "reason": "barge-in",
                                    "voice_session_id": voice_session_id,
                                    "turn_id": voice_turn_id,
                                },
                                model_name=effective_model_name,
                                user_registration=(
                                    "anonymous"
                                    if request_flags["anonymous_user"]
                                    else "registered"
                                ),
                            )
                            break
                        delta_text = str(delta)
                        if not delta_text:
                            continue
                        raw_parts.append(delta_text)
                        stream_emitted_delta = True
                        await self._emit_stream_event(
                            event_sink,
                            req_env,
                            "text_delta",
                            payload={"delta": delta_text},
                            model_name=effective_model_name,
                            user_registration=(
                                "anonymous"
                                if request_flags["anonymous_user"]
                                else "registered"
                            ),
                        )
                        for chunk in chunker.add_delta(delta_text):
                            speech_chunks.append(chunk)
                            await self._emit_stream_event(
                                event_sink,
                                req_env,
                                "text_chunk",
                                payload={
                                    "chunk": chunk,
                                    "session_id": session_id,
                                    "voice_session_id": voice_session_id,
                                    "turn_id": voice_turn_id,
                                },
                                model_name=effective_model_name,
                                user_registration=(
                                    "anonymous"
                                    if request_flags["anonymous_user"]
                                    else "registered"
                                ),
                            )
                except Exception as e:
                    _log_exception("LLM backend stream failed", e)
                    await self._emit_stream_event(
                        event_sink,
                        req_env,
                        "stream_error",
                        payload={
                            "voice_session_id": voice_session_id,
                            "turn_id": voice_turn_id,
                        },
                        model_name=effective_model_name,
                        user_registration=(
                            "anonymous"
                            if request_flags["anonymous_user"]
                            else "registered"
                        ),
                        error={
                            "code": "LLM_BACKEND_ERROR",
                            "message": str(e),
                        },
                    )
                    err = {
                        "v": 1, "type": "response", "id": new_id("res"),
                        "reply_to": req_env.get("id"), "ts": iso_now(), "route": "orac.prompt",
                        "meta": {
                            "status": "error",
                            "model": effective_model_name,
                            "req_id": req_env.get("id"),
                            "llm_source": effective_llm_source,
                        },
                        "payload": None,
                        "error": {"code": "LLM_BACKEND_ERROR", "message": str(e)},
                    }
                    return json.dumps(err, ensure_ascii=False)

                final_chunk = "" if stream_cancelled else chunker.flush()
                if final_chunk:
                    speech_chunks.append(final_chunk)
                    await self._emit_stream_event(
                        event_sink,
                        req_env,
                        "text_chunk",
                        payload={
                            "chunk": final_chunk,
                            "session_id": session_id,
                            "voice_session_id": voice_session_id,
                            "turn_id": voice_turn_id,
                        },
                        model_name=effective_model_name,
                        user_registration=(
                            "anonymous"
                            if request_flags["anonymous_user"]
                            else "registered"
                        ),
                    )
                raw = "".join(raw_parts).strip()
                if not stream_cancelled and stream_usage is not None:
                    if stream_usage.prompt_tokens is not None:
                        prompt_tokens = stream_usage.prompt_tokens
                    if stream_usage.completion_tokens is not None:
                        completion_tokens = stream_usage.completion_tokens
                    if stream_usage.total_tokens is not None:
                        total_tokens = stream_usage.total_tokens
                        tokens_used = stream_usage.total_tokens
            else:
                # === Call backend (non-streaming path) ===
                try:
                    prompt_result = llm_connector.send_prompt_with_meta(
                        prompt_type="U",
                        prompt=final_prompt,
                        stream=False,
                        generation_options=generation_options,
                    )
                except Exception as e:
                    _log_exception("LLM backend call failed", e)
                    err = {
                        "v": 1, "type": "response", "id": new_id("res"),
                        "reply_to": req_env.get("id"), "ts": iso_now(), "route": "orac.prompt",
                        "meta": {
                            "status": "error",
                            "model": effective_model_name,
                            "req_id": req_env.get("id"),
                            "llm_source": effective_llm_source,
                        },
                        "payload": None,
                        "error": {"code": "LLM_BACKEND_ERROR", "message": str(e)},
                    }
                    return json.dumps(err, ensure_ascii=False)

                # Normalise: ensure string
                raw = str(prompt_result.get("text") or "").strip()
                prompt_tokens = int(prompt_result.get("prompt_tokens") or 0)
                completion_tokens = int(prompt_result.get("completion_tokens") or 0)
                total_tokens = int(prompt_result.get("total_tokens") or 0)
                tokens_used = total_tokens or None

            # Apply local reasoning-strip unless explicitly requested
            if show_reasoning:
                content = raw
            else:
                stripped = self._strip_reasoning_tags(raw)
                content = stripped if stripped else raw

            if retrieval_pack is not None:
                content = polish_retrieval_response_text(
                    content,
                    response_style=(
                        meta.get("retrieval_response_style")
                        or getattr(self, "_retrieval_response_style", "normal")
                    ),
                    retrieval_pack=retrieval_pack,
                    retrieval_outcome=retrieval_outcome,
                )

            if not content:
                logger.log_warning("Backend returned empty content after stripping; using friendly fallback.")
                content = "Hello! 👋"

            if stream_requested and not stream_cancelled and stream_emitted_delta:
                missing_speech = self._missing_stream_speech_suffix(
                    content=content,
                    speech_chunks=speech_chunks,
                )
                if missing_speech:
                    logger.log_warning(
                        "Streaming speech chunks missed final response suffix; "
                        "queuing fallback speech chunk."
                    )
                    await self._emit_stream_event(
                        event_sink,
                        req_env,
                        "text_chunk",
                        payload={
                            "chunk": missing_speech,
                            "session_id": session_id,
                            "voice_session_id": voice_session_id,
                            "turn_id": voice_turn_id,
                        },
                        model_name=effective_model_name,
                        user_registration=(
                            "anonymous"
                            if request_flags["anonymous_user"]
                            else "registered"
                        ),
                    )
                    speech_chunks.append(missing_speech)

            if stream_requested and not stream_cancelled and not stream_emitted_delta and content:
                await self._emit_stream_event(
                    event_sink,
                    req_env,
                    "text_delta",
                    payload={"delta": content},
                    model_name=effective_model_name,
                    user_registration=(
                        "anonymous" if request_flags["anonymous_user"] else "registered"
                    ),
                )
                await self._emit_stream_event(
                    event_sink,
                    req_env,
                    "text_chunk",
                    payload={
                        "chunk": content,
                        "session_id": session_id,
                        "voice_session_id": voice_session_id,
                        "turn_id": voice_turn_id,
                    },
                    model_name=effective_model_name,
                    user_registration=(
                        "anonymous" if request_flags["anonymous_user"] else "registered"
                    ),
                )

            # --- Save ASSISTANT turn -------------------------------------------
            if retrieval_pack is not None:
                self._remember_retrieval_context(
                    session_id,
                    user_message=prompt,
                    previous_context=previous_retrieval_context,
                    retrieval_decision=retrieval_decision,
                    retrieval_outcome=retrieval_outcome,
                    retrieval_pack=retrieval_pack,
                )
            last_ti = self._save_assistant_turn(
                session_id,
                auth_user,
                content,
                client=client,
                req_id=req_env.get("id"),
                show_reasoning=show_reasoning,
                llm_id=effective_llm_id,
                tokens_used=tokens_used,
                request_flags=request_flags,
            )

            self._maybe_set_conversation_title(session_id, meta, llm_connector)
            self._maybe_prune(session_id, last_ti)

            resp_env = self._build_response(
                req_env,
                content,
                stop_reason="error" if stream_cancelled else "stop",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model_name=effective_model_name,
                user_registration=(
                    "anonymous" if request_flags["anonymous_user"] else "registered"
                ),
            )

            if stream_requested and not stream_cancelled:
                await self._emit_stream_event(
                    event_sink,
                    req_env,
                    "stream_end",
                    payload={
                        "stop_reason": "stop",
                        "voice_session_id": voice_session_id,
                        "turn_id": voice_turn_id,
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": prompt_tokens + completion_tokens,
                        },
                    },
                    model_name=effective_model_name,
                    user_registration=(
                        "anonymous" if request_flags["anonymous_user"] else "registered"
                    ),
                )

            wire = json.dumps(resp_env, ensure_ascii=False)
            logger.log_debug(f"Returning response frame: {wire[:300]}{'…' if len(wire) > 300 else ''}")
            if stream_cancelled:
                self._clear_voice_turn_cancelled(
                    session_id=voice_session_id,
                    turn_id=voice_turn_id,
                )
            return wire

        except Exception as e:
            _log_exception("Error while processing request", e)
            err_env = {
                "v": 1, "type": "response", "id": new_id("res"),
                "reply_to": req_env.get("id") if isinstance(req_env, dict) else None,
                "ts": iso_now(), "route": "orac.prompt",
                "meta": {
                    "status": "error",
                    "model": self.model_name,
                    "llm_source": getattr(self, "_active_llm_source", None),
                },
                "payload": None, "error": {"code": "SERVER_ERROR", "message": str(e)},
            }
            return json.dumps(err_env, ensure_ascii=False)



# --- Module-level main() runner ----------------------------------------------
async def main():
    orchestrator = None
    try:
        orchestrator = Orac()
        listener = OracListener(orchestrator=orchestrator, host="127.0.0.1", port=8765)
        await listener.start_server()
    except Exception as e:
        _log_exception("Fatal in main()", e)
        raise
    finally:
        if orchestrator is not None:
            orchestrator.shutdown()


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
