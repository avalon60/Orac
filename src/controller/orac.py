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

    return f"{policy['title']}\n{_render_policy_lines(lines)}\n"



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
            prefs = {
                "timezone": meta.get("timezone", "Europe/London"),
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

            primer_inline = _orac_system_primer({
                "reply_language": meta.get("reply_language", self._reply_language)
            }, self._system_prompt_policy)

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
                if self.enable_prompt_dump:
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

            if self.enable_prompt_dump:
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
                "Use 'Recent exchange' as session memory for THIS conversation. "
                "If it contains explicit facts that answer the question, use the most recent consistent fact. "
                "If not present or ambiguous, say you don't know and optionally ask the user to clarify. "
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

            if self.enable_prompt_dump:
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
        if meta.get("weather_location"):
            return meta

        try:
            weather_pref = self.ctx.get_user_preference_value(
                username=auth_user,
                pref_key="weather_location",
            )
        except Exception as e:
            _log_exception("Failed to load weather_location preference", e)
            return meta

        if not isinstance(weather_pref, dict):
            return meta

        name = str(weather_pref.get("name") or "").strip()
        if not name:
            return meta

        parts = [name]
        admin1 = str(weather_pref.get("admin1") or "").strip()
        country = str(weather_pref.get("country") or "").strip()
        if admin1:
            parts.append(admin1)
        if country:
            parts.append(country)

        enriched_meta = dict(meta)
        enriched_meta["weather_location"] = ", ".join(parts)
        enriched_meta["weather_location_pref"] = weather_pref
        return enriched_meta

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
            save_res_a = self.ctx.save_assistant_turn(session_id, auth_user, content, meta=asst_meta)
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
                        user_registration: str = "registered") -> dict:
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
            meta = self._apply_user_preference_meta(meta, auth_user)

            logger.log_info(f"{Icons.info} [{client}] user={auth_user} Prompt received")
            logger.log_debug(f"Prompt text: {prompt}")
            logger.log_info(f"meta.show_reasoning={show_reasoning} (strip_reasoning_default={self.strip_reasoning_tags})")
            request_flags = {"anonymous_user": False}

            try:
                self._ensure_db_session_ready()
            except Exception as e:
                _log_exception("Oracle session validation failed (non-fatal)", e)

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

            # Prefer timeout-aware conversation rollover. If anything goes wrong,
            # fall back to the non-timeout path and keep going.
            try:
                roll = self.ctx.ensure_conversation_with_timeout(
                    user_name=auth_user,
                    session_id_base=session_id_base,
                    llm_id=None,
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
                try:
                    self.ctx.ensure_conversation(user_name=auth_user, session_id=session_id, llm_id=None)
                except Exception as e2:
                    if self._is_unregistered_user_error(e2):
                        request_flags["anonymous_user"] = True
                    _log_exception("ensure_conversation fallback failed (non-fatal)", e2)

            # --- Ensure a system primer is stored once per conversation ---------
            try:
                if self.ctx.last_turn_index(session_id) == 0:
                    primer = _orac_system_primer(
                        {"reply_language": self._reply_language},
                        self._system_prompt_policy,
                    )
                    self.ctx.save_system_turn(session_id, auth_user, primer, meta={
                        "kind": "primer",
                        "ts": iso_now(),
                        "protocol_version": PROTOCOL_VERSION,
                    })
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
                save_res_u = self.ctx.save_user_turn(session_id, auth_user, prompt, meta=user_meta)
                logger.log_debug(f"Saved user msg: {save_res_u}")
            except Exception as e:
                if self._is_unregistered_user_error(e):
                    request_flags["anonymous_user"] = True
                self._handle_persistence_failure("user_turn", e)

            plugin_routing_handoff = self._collect_plugin_routing_handoff(prompt, meta)
            plugin_execution_result = None
            if self.plugin_router is not None:
                plugin_execution_result = self.plugin_router.route(prompt, meta, plugin_routing_handoff)

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
                    request_flags=request_flags,
                )
                self._maybe_set_conversation_title(session_id, meta)
                self._maybe_prune(session_id, last_ti)
                resp_env = self._build_response(
                    req_env,
                    content,
                    stop_reason=plugin_execution_result.stop_reason,
                    prompt_tokens=0,
                    completion_tokens=0,
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
                request_flags=request_flags,
            )

            self._maybe_set_conversation_title(session_id, meta)
            self._maybe_prune(session_id, last_ti)

            resp_env = self._build_response(
                req_env,
                content,
                stop_reason="stop",
                prompt_tokens=0,
                completion_tokens=0,
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
