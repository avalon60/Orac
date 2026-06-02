"""Tests for Orac context continuity and persistence visibility.

# Author: Clive Bostock
# Date: 2026-04-26
# Description: Verifies current Orac context continuity across normal and
#   plugin-handled turns without redesigning the runtime flow.
"""

from __future__ import annotations

from decimal import Decimal
import json
import re
from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone
import types
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

if "langchain_openai" not in sys.modules:
    stub_module = types.ModuleType("langchain_openai")

    class _StubChatOpenAI:  # pragma: no cover - import shim for test isolation
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def invoke(self, prompt):
            return prompt

    stub_module.ChatOpenAI = _StubChatOpenAI
    sys.modules["langchain_openai"] = stub_module

if "oracledb" not in sys.modules:
    stub_oracledb = types.ModuleType("oracledb")

    class _StubConnection:
        pass

    class _StubDatabaseError(Exception):
        pass

    stub_oracledb.Connection = _StubConnection
    stub_oracledb.DatabaseError = _StubDatabaseError
    stub_oracledb.NUMBER = object()
    sys.modules["oracledb"] = stub_oracledb

import controller.orac as orac_module
from controller.orac import Orac
from model.context_manager import OracContextManager
from model.llm_connector import LLMUsageMetadata
from model.plugin_runtime import PluginExecutionResult
from orac_core.retrieval import FetchedSource
from orac_core.retrieval import GroundingPackBuilder
from orac_core.retrieval import GroundingPack
from orac_core.retrieval import RetrievalDecision
from orac_core.retrieval import RetrievalDecisionService
from orac_core.retrieval import RetrievalOutcome
from orac_core.retrieval import RetrievalSettings
from orac_core.retrieval import RetrievalTurnContext
from orac_core.retrieval import SearchRequest
from orac_core.retrieval import SearchResult


class _FakeLogger:
    """Captures logger calls for assertions."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def log_debug(self, message: str) -> None:
        self.messages.append(("debug", message))

    def log_info(self, message: str) -> None:
        self.messages.append(("info", message))

    def log_warning(self, message: str) -> None:
        self.messages.append(("warning", message))

    def log_error(self, message: str) -> None:
        self.messages.append(("error", message))

    def log_critical(self, message: str) -> None:
        self.messages.append(("critical", message))


class _AuthResult:
    """Represents a successful authentication result for tests."""

    def __init__(self, user: str = "clive") -> None:
        self.ok = True
        self.user = user
        self.reason = None


class _FakeAuthChain:
    """Always authenticates as the configured user."""

    def __init__(self, user: str = "clive") -> None:
        self._user = user

    def authenticate(self, req_env: dict) -> _AuthResult:
        del req_env
        return _AuthResult(self._user)


class _FakeLLM:
    """Captures prompts and returns queued responses."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.prompts: list[str] = []
        self.generation_options_seen: list[dict | None] = []
        self.stream_usage_metadata: LLMUsageMetadata | None = None

    def send_prompt(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
        generation_options: dict | None = None,
    ) -> str:
        del prompt_type, stream
        self.prompts.append(prompt)
        self.generation_options_seen.append(generation_options)
        if self._responses:
            return self._responses.pop(0)
        return "stubbed response"

    def send_prompt_with_meta(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
        generation_options: dict | None = None,
    ) -> dict[str, int | str]:
        text = self.send_prompt(
            prompt_type=prompt_type,
            prompt=prompt,
            stream=stream,
            generation_options=generation_options,
        )
        return {
            "text": text,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    def stream_prompt_deltas(
        self,
        prompt_type: str,
        prompt: str,
        generation_options: dict | None = None,
        on_usage_metadata=None,
    ):
        """Yield a queued response as one streaming delta."""
        text = self.send_prompt(
            prompt_type=prompt_type,
            prompt=prompt,
            stream=True,
            generation_options=generation_options,
        )
        yield text
        if self.stream_usage_metadata is not None and on_usage_metadata is not None:
            on_usage_metadata(self.stream_usage_metadata)


class _ProbeLLM:
    """Returns probe responses based on the prompt content."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def send_prompt_with_meta(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
        generation_options: dict | None = None,
    ) -> dict[str, int | str]:
        del prompt_type, stream, generation_options
        self.prompts.append(prompt)
        if (
            "and nothing else" in prompt
            and "Conversation context" not in prompt
        ):
            return {
                "text": "ACK",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }

        match = re.search(r"ORAC-PROBE-[^-]+-[A-Fa-f0-9]{8}", prompt)
        token = match.group(0) if match else "ORAC-PROBE-UNKNOWN"
        return {
            "text": token,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }


class _ProbeLLMShouldNotBeCalled:
    """LLM stub that fails if a chat probe is attempted."""

    def __init__(self) -> None:
        self.calls = 0

    def send_prompt_with_meta(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
        generation_options: dict | None = None,
    ) -> dict[str, int | str]:
        del prompt_type, prompt, stream, generation_options
        self.calls += 1
        raise AssertionError("chat probe should not run for non-chat models")


class _ProbeLLMBackendFailure:
    """LLM stub that simulates a backend probe failure."""

    def send_prompt_with_meta(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
        generation_options: dict | None = None,
    ) -> dict[str, int | str]:
        del prompt_type, prompt, stream, generation_options
        raise RuntimeError("404 Client Error: Not Found for url")


class _UnavailableRetrievalService:
    """Retrieval stub that reports explicit retrieval failure."""

    default_search_provider = "searxng"

    def __init__(self, message: str) -> None:
        self.message = message
        self.prompts: list[str] = []

    def build_grounding_outcome(
        self,
        prompt: str,
        *,
        event_emitter=None,
    ) -> RetrievalOutcome:
        """Return an unavailable retrieval outcome."""
        self.prompts.append(prompt)
        if callable(event_emitter):
            event_emitter(
                "retrieval_failed",
                {"mode": "internet", "reason": "no_search_results"},
            )
        return RetrievalOutcome(
            requested=True,
            status="no_search_results",
            message=self.message,
        )

    def build_grounding_outcome_for_request(
        self,
        request: RetrievalDecision,
        *,
        event_emitter=None,
    ) -> RetrievalOutcome:
        """Return an unavailable retrieval outcome for a supplied request."""
        self.prompts.append(str(getattr(request, "query", "")))
        if callable(event_emitter):
            event_emitter(
                "retrieval_failed",
                {"mode": "internet", "reason": "no_search_results"},
            )
        return RetrievalOutcome(
            requested=True,
            status="no_search_results",
            message=self.message,
        )


class _SuccessfulRetrievalService:
    """Retrieval stub that returns a grounded explicit retrieval outcome."""

    default_search_provider = "searxng"

    def __init__(self, pack) -> None:
        self.pack = pack
        self.prompts: list[str] = []

    def build_grounding_outcome(
        self,
        prompt: str,
        *,
        event_emitter=None,
    ) -> RetrievalOutcome:
        """Return a successful retrieval outcome with grounded evidence."""
        self.prompts.append(prompt)
        self._emit_lifecycle_events(event_emitter)
        return RetrievalOutcome(
            requested=True,
            status="ok",
            message="Online evidence was retrieved for the explicit request.",
            grounding_pack=self.pack,
        )

    def build_grounding_outcome_for_request(
        self,
        request: RetrievalDecision,
        *,
        event_emitter=None,
    ) -> RetrievalOutcome:
        """Return a successful retrieval outcome for a supplied request."""
        self.prompts.append(str(getattr(request, "query", "")))
        self._emit_lifecycle_events(event_emitter)
        return RetrievalOutcome(
            requested=True,
            status="ok",
            message="Online evidence was retrieved for the request.",
            grounding_pack=self.pack,
        )

    def _emit_lifecycle_events(self, event_emitter) -> None:
        """Emit a standard retrieval lifecycle sequence for tests."""
        if not callable(event_emitter):
            return
        search_result_count = len(getattr(self.pack, "search_results", ()) or ())
        fetched_source_count = len(getattr(self.pack, "fetched_sources", ()) or ())
        usable_source_count = len(getattr(self.pack, "grounding_sources", ()) or ())
        event_emitter(
            "retrieval_fetch_start",
            {"source_count": search_result_count},
        )
        event_emitter(
            "retrieval_fetch_complete",
            {
                "fetched_count": fetched_source_count,
                "usable_source_count": usable_source_count,
            },
        )
        event_emitter(
            "retrieval_complete",
            {
                "source_count": search_result_count,
                "usable_source_count": usable_source_count,
            },
        )


class _TopicAwareRetrievalService:
    """Retrieval stub that returns topic-specific grounded outcomes."""

    default_search_provider = "searxng"

    def __init__(self, packs_by_topic: dict[str, GroundingPack]) -> None:
        self.packs_by_topic = {
            str(key).strip().lower(): value for key, value in packs_by_topic.items()
        }
        self.prompts: list[str] = []

    def _pack_for_text(self, text: str) -> RetrievalOutcome:
        lowered = str(text or "").lower()
        if "ukraine" in lowered or "russia" in lowered or "kyiv" in lowered:
            pack = self.packs_by_topic.get("ukraine")
        elif "iran" in lowered or "tehran" in lowered or "hormuz" in lowered:
            pack = self.packs_by_topic.get("iran")
        elif "python" in lowered:
            pack = self.packs_by_topic.get("python")
        elif "searxng" in lowered:
            pack = self.packs_by_topic.get("searxng")
        elif "israel" in lowered or "gaza" in lowered:
            pack = self.packs_by_topic.get("israel")
        else:
            pack = None

        if pack is None:
            return RetrievalOutcome(
                requested=True,
                status="no_relevant_sources",
                message="I could not find online evidence relevant to that topic.",
            )

        return RetrievalOutcome(
            requested=True,
            status="ok",
            message="Online evidence was retrieved for the request.",
            grounding_pack=pack,
        )

    def build_grounding_outcome(self, prompt: str, *, event_emitter=None) -> RetrievalOutcome:
        """Return a topic-aware retrieval outcome for a prompt."""
        self.prompts.append(prompt)
        if callable(event_emitter):
            event_emitter("retrieval_fetch_start", {"source_count": 1})
            event_emitter(
                "retrieval_fetch_complete",
                {"fetched_count": 1, "usable_source_count": 1},
            )
            event_emitter(
                "retrieval_complete",
                {"source_count": 1, "usable_source_count": 1},
            )
        return self._pack_for_text(prompt)

    def build_grounding_outcome_for_request(
        self,
        request: SearchRequest,
        *,
        event_emitter=None,
    ) -> RetrievalOutcome:
        """Return a topic-aware retrieval outcome for a request."""
        query = str(getattr(request, "query", "") or "")
        self.prompts.append(query)
        if callable(event_emitter):
            event_emitter("retrieval_fetch_start", {"source_count": 1})
            event_emitter(
                "retrieval_fetch_complete",
                {"fetched_count": 1, "usable_source_count": 1},
            )
            event_emitter(
                "retrieval_complete",
                {"source_count": 1, "usable_source_count": 1},
            )
        return self._pack_for_text(query)


class _TopicSensitiveLLM:
    """Returns topic-specific answers by inspecting the prompt evidence."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def send_prompt_with_meta(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
        generation_options: dict | None = None,
    ) -> dict[str, int | str]:
        del prompt_type, stream, generation_options
        self.prompts.append(prompt)
        lowered = prompt.lower()
        if "ukraine" in lowered or "kyiv" in lowered or "zelensky" in lowered:
            text = "Ukraine-focused latest news answer."
        elif "iran" in lowered or "tehran" in lowered or "hormuz" in lowered:
            text = "Iran-focused latest news answer."
        elif "python" in lowered:
            text = "Python-focused latest release answer."
        elif "searxng" in lowered:
            text = "SearXNG-focused latest version answer."
        else:
            text = "General answer."
        return {
            "text": text,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }


class _StaticRetrievalDecisionService:
    """Decision stub that returns a preconfigured retrieval decision."""

    def __init__(self, decision: RetrievalDecision) -> None:
        self.decision = decision
        self.prompts: list[str] = []

    def decide(
        self,
        prompt: str,
        *,
        previous_context=None,
    ) -> RetrievalDecision:
        """Return the configured retrieval decision."""
        del previous_context
        self.prompts.append(prompt)
        return self.decision


class _MemoryContextManager:
    """Small in-memory stand-in for Orac context persistence."""

    def __init__(self, fail_role: str | None = None) -> None:
        self.fail_role = fail_role
        self.messages_by_session: dict[str, list[dict[str, str]]] = {}
        self.conversation_ids: dict[str, int] = {}
        self.conversation_llm_ids: dict[str, int | None] = {}
        self.closed_sessions: list[str] = []
        self.archived_sessions: list[str] = []
        self.system_metas_by_session: dict[str, list[dict]] = {}
        self.user_preferences: dict[tuple[str, str], str] = {}
        self.llm_registry_entries: dict[int, dict[str, object]] = {
            1: {
                "LLM_ID": 1,
                "PROVIDER": "ollama",
                "MODEL": "test-model",
                "IS_ENABLED": "Y",
            }
        }
        self.personalities: dict[str, dict[str, object]] = {}
        self.model_generation_presets: dict[int, dict[str, object]] = {}
        self.titles: dict[str, str] = {}
        self.ensure_calls: list[tuple[str, str, int]] = []
        self.saved_events: list[tuple[str, str, str]] = []
        self._next_conversation_id = 1

    def ensure_conversation_with_timeout(
        self,
        *,
        user_name: str,
        session_id_base: str,
        llm_id: int | None,
        timeout_seconds: int,
    ) -> dict:
        del timeout_seconds
        if session_id_base not in self.conversation_ids:
            self.conversation_ids[session_id_base] = self._next_conversation_id
            self._next_conversation_id += 1
            self.messages_by_session.setdefault(session_id_base, [])
            self.conversation_llm_ids[session_id_base] = llm_id
        cid = self.conversation_ids[session_id_base]
        self.ensure_calls.append((user_name, session_id_base, cid))
        return {
            "conversation_id": cid,
            "session_id": session_id_base,
            "rolled_over": False,
            "age_seconds": 0.0,
            "previous_conversation_id": cid,
            "previous_session_id": session_id_base,
        }

    def ensure_conversation(self, *, user_name: str, session_id: str, llm_id: int | None = None) -> int:
        del user_name
        if session_id not in self.conversation_ids:
            self.conversation_ids[session_id] = self._next_conversation_id
            self._next_conversation_id += 1
            self.messages_by_session.setdefault(session_id, [])
            self.conversation_llm_ids[session_id] = llm_id
        elif llm_id is not None and session_id not in self.conversation_llm_ids:
            self.conversation_llm_ids[session_id] = llm_id
        return self.conversation_ids[session_id]

    def _save(
        self,
        session_id: str,
        role: str,
        text: str,
        *,
        meta: dict | None = None,
        tokens_used=None,
    ) -> dict[str, int]:
        if self.fail_role == role:
            raise RuntimeError(f"Simulated {role} persistence failure")
        bucket = self.messages_by_session.setdefault(session_id, [])
        turn_index = len(bucket) + 1
        bucket.append(
            {
                "role": role,
                "content": text,
                "meta": meta or {},
                "tokens_used": tokens_used,
            }
        )
        if role == "system":
            self.system_metas_by_session.setdefault(session_id, []).append(
                meta or {}
            )
        self.saved_events.append((session_id, role, text))
        return {
            "conversation_id": self.conversation_ids.setdefault(session_id, self._next_conversation_id),
            "message_id": turn_index,
            "turn_index": turn_index,
        }

    def last_turn_index(self, session_id: str) -> int:
        return len(self.messages_by_session.get(session_id, []))

    def save_system_turn(self, session_id: str, user_name: str, text: str, *, meta=None, llm_id=None) -> dict[str, int]:
        del user_name, llm_id
        return self._save(session_id, "system", text, meta=meta)

    def save_user_turn(
        self,
        session_id: str,
        user_name: str,
        text: str,
        *,
        meta=None,
        llm_id=None,
        tokens_used=None,
    ) -> dict[str, int]:
        del user_name, llm_id
        return self._save(session_id, "user", text, meta=meta, tokens_used=tokens_used)

    def save_assistant_turn(
        self,
        session_id: str,
        user_name: str,
        text: str,
        *,
        meta=None,
        llm_id=None,
        tokens_used=None,
    ) -> dict[str, int]:
        del user_name, llm_id
        return self._save(
            session_id,
            "assistant",
            text,
            meta=meta,
            tokens_used=tokens_used,
        )

    def get_messages_for_prompt(self, session_id: str, limit: int = 20) -> list[dict[str, str]]:
        del limit
        return list(self.messages_by_session.get(session_id, []))

    def get_user_profile(self, username: str) -> dict[str, str]:
        return {
            "authenticated_username": username,
            "display_name": "Clive",
        }

    def get_user_preference_value(self, *args, **kwargs) -> str | None:
        username = kwargs.get("username")
        pref_key = kwargs.get("pref_key")
        if username is None and args:
            username = args[0]
        if pref_key is None and len(args) > 1:
            pref_key = args[1]
        return self.user_preferences.get((str(username), str(pref_key)))

    def get_orac_personality(self, personality_code: str) -> dict[str, str] | None:
        return self.personalities.get(str(personality_code).strip().upper())

    def get_model_generation_preset(
        self,
        *,
        model_preset_id=None,
        model_preset_code=None,
    ) -> dict[str, object]:
        del model_preset_code
        if model_preset_id in (None, ""):
            return {}
        return self.model_generation_presets.get(int(model_preset_id), {})

    def get_llm_registry_entry_by_provider_model(
        self,
        provider: str,
        model: str,
    ) -> dict[str, object]:
        return {
            "LLM_ID": 1,
            "PROVIDER": provider,
            "MODEL": model,
            "IS_ENABLED": "Y",
        }

    def get_llm_registry_entry(self, llm_id: int | str) -> dict[str, object]:
        return self.llm_registry_entries.get(int(llm_id), {})

    def prune_context(
        self,
        session_id: str,
        *,
        keep_messages: int = 100,
        archive_conversation: bool = False,
    ) -> int:
        del archive_conversation
        bucket = self.messages_by_session.get(session_id, [])
        if len(bucket) <= keep_messages:
            return 0
        deleted = len(bucket) - keep_messages
        self.messages_by_session[session_id] = bucket[-keep_messages:]
        return deleted

    def get_conversation_title(self, session_id: str) -> str | None:
        return self.titles.get(session_id)

    def get_conversation_personality_code(self, session_id: str) -> str:
        del session_id
        return "DEFAULT"

    def get_conversation_prompt_policy_fingerprint(
        self,
        session_id: str,
    ) -> str | None:
        metas = self.system_metas_by_session.get(session_id) or []
        if not metas:
            return None
        value = metas[0].get("prompt_policy_fingerprint")
        return str(value).strip() if value else None

    def get_conversation_llm_id(self, session_id: str) -> int | None:
        return self.conversation_llm_ids.get(session_id)

    def set_conversation_title(self, session_id: str, title: str) -> None:
        self.titles[session_id] = title

    def archive_conversation(self, session_id: str) -> None:
        self.archived_sessions.append(session_id)

    def close_conversation(self, session_id: str) -> None:
        self.closed_sessions.append(session_id)


class _AnonymousContextManager(_MemoryContextManager):
    """Context manager stub that simulates an unregistered authenticated user."""

    def ensure_conversation_with_timeout(
        self,
        *,
        user_name: str,
        session_id_base: str,
        llm_id: int | None,
        timeout_seconds: int,
    ) -> dict:
        del user_name, session_id_base, llm_id, timeout_seconds
        raise PermissionError("user 'clive' is not registered")

    def ensure_conversation(self, *, user_name: str, session_id: str, llm_id: int | None = None) -> int:
        del user_name, session_id, llm_id
        raise PermissionError("user 'clive' is not registered")

    def last_turn_index(self, session_id: str) -> int:
        del session_id
        return 0

    def save_system_turn(self, session_id: str, user_name: str, text: str, *, meta=None, llm_id=None) -> dict[str, int]:
        del session_id, user_name, text, meta, llm_id
        raise PermissionError("user 'clive' is not registered")

    def save_user_turn(
        self,
        session_id: str,
        user_name: str,
        text: str,
        *,
        meta=None,
        llm_id=None,
        tokens_used=None,
    ) -> dict[str, int]:
        del session_id, user_name, text, meta, llm_id, tokens_used
        raise PermissionError("user 'clive' is not registered")

    def save_assistant_turn(
        self,
        session_id: str,
        user_name: str,
        text: str,
        *,
        meta=None,
        llm_id=None,
        tokens_used=None,
    ) -> dict[str, int]:
        del session_id, user_name, text, meta, llm_id, tokens_used
        raise PermissionError("user 'clive' is not registered")

    def get_messages_for_prompt(self, session_id: str, limit: int = 20) -> list[dict[str, str]]:
        del session_id, limit
        return []

    def get_user_profile(self, username: str) -> dict[str, str]:
        del username
        return {}


class _ConditionalPluginRouter:
    """Returns a handled weather result only for the Brigadoon weather turn."""

    def __init__(self, weather_content: str) -> None:
        self.weather_content = weather_content
        self.calls: list[str] = []

    def route(
        self,
        prompt: str,
        meta: dict,
        handoff,
        auth_user: str | None = None,
        *,
        audit_adapter=None,
        request_context=None,
    ) -> PluginExecutionResult | None:
        del meta, handoff, auth_user, audit_adapter, request_context
        self.calls.append(prompt)
        if prompt == "What is the weather like in Brigadoon?":
            return PluginExecutionResult(plugin_id="weather", content=self.weather_content)
        return None


class _FakeDBSession:
    """Minimal DB stub to exercise load_context limit semantics."""

    def __init__(self) -> None:
        self.rows = [
            {"TURN_INDEX": 1, "ROLE": "user", "CONTENT": {"text": "one"}, "TOKENS_USED": None, "META": {}, "CREATED_ON": "t1"},
            {"TURN_INDEX": 2, "ROLE": "assistant", "CONTENT": {"text": "two"}, "TOKENS_USED": None, "META": {}, "CREATED_ON": "t2"},
            {"TURN_INDEX": 3, "ROLE": "user", "CONTENT": {"text": "three"}, "TOKENS_USED": None, "META": {}, "CREATED_ON": "t3"},
            {"TURN_INDEX": 4, "ROLE": "assistant", "CONTENT": {"text": "four"}, "TOKENS_USED": None, "META": {}, "CREATED_ON": "t4"},
            {"TURN_INDEX": 5, "ROLE": "user", "CONTENT": {"text": "five"}, "TOKENS_USED": None, "META": {}, "CREATED_ON": "t5"},
        ]

    def dict_sql_dataset(self, sql: str, params: dict) -> list[dict]:
        del params
        if "order by turn_index desc" in sql and "fetch first 2 rows only" in sql:
            picked = list(reversed(self.rows))[:2]
            return sorted(picked, key=lambda row: row["TURN_INDEX"])
        if "fetch first 2 rows only" in sql:
            return self.rows[:2]
        return list(self.rows)


class _SyncCursor:
    """Captures registry sync update statements for assertions."""

    def __init__(self) -> None:
        self.statements: list[tuple[str, dict]] = []

    def __enter__(self) -> "_SyncCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False

    def execute(self, sql: str, params: dict) -> None:
        self.statements.append((sql, params))


class _SyncDBSession:
    """DB stub for llm registry sync tests."""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.cursor_obj = _SyncCursor()
        self.committed = False

    def dict_sql_dataset(self, sql: str) -> list[dict]:
        del sql
        return list(self.rows)

    def cursor(self) -> _SyncCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        return None


class _ProbeCursor:
    """Captures probe update statements for assertions."""

    def __init__(self) -> None:
        self.statements: list[tuple[str, dict]] = []

    def __enter__(self) -> "_ProbeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        del exc_type, exc, tb
        return False

    def execute(self, sql: str, params: dict) -> None:
        self.statements.append((sql, params))


class _ProbeDBSession:
    """DB stub for unresolved LLM probe tests."""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.cursor_obj = _ProbeCursor()
        self.committed = False
        self.closed = False

    def dict_sql_dataset(self, sql: str) -> list[dict]:
        del sql
        return list(self.rows)

    def cursor(self) -> _ProbeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


class _TimeoutDBSession:
    """DB stub for timeout rollover decisions."""

    def __init__(self, last_ts: datetime) -> None:
        self.last_ts = last_ts

    def dict_sql_dataset(self, sql: str, params: dict) -> list[dict]:
        del params
        if "select user_id from" in sql.lower():
            return [{"USER_ID": 7}]
        if "select conv_id" in sql.lower():
            return [
                {
                    "CONV_ID": 99,
                    "SESSION_ID": "clive#existing",
                    "LAST_TS": self.last_ts,
                }
            ]
        return []


class _HealthCheckDBSession:
    """DB session stub that can fail a health check before reconnect."""

    def __init__(self, *, fail_once: bool = False) -> None:
        self.fail_once = fail_once
        self.health_checks = 0

    def fetch_as_lists(self, sql: str, bind_mappings: dict | None = None) -> list[list[int]]:
        del bind_mappings
        self.health_checks += 1
        if sql == "select 1 from dual" and self.fail_once:
            self.fail_once = False
            raise RuntimeError("DPY-1001: not connected to database")
        return [[1]]

    def close(self) -> None:
        return None


class OracContextHistoryTests(unittest.IsolatedAsyncioTestCase):
    """Tests runtime continuity for normal and plugin-handled turns."""

    def test_clock_context_prioritises_user_facing_local_time(self) -> None:
        """Clock context should tell the model to answer in local time."""
        clock = orac_module.system_clock_line({"timezone": "Europe/London"})

        local_index = clock.index("User-facing local time:")
        utc_index = clock.index("Current UTC time for logs")

        self.assertLess(local_index, utc_index)
        self.assertIn(
            "use the user-facing local time above, not UTC",
            clock,
        )
        self.assertIn(
            "The user-facing local time is authoritative for the current turn",
            clock,
        )
        self.assertIn(
            "answer with the exact HH:MM value",
            clock,
        )
        self.assertIn(
            "Do not round to the hour or omit minutes",
            clock,
        )

    def test_clock_context_uses_weather_location_for_where_are_you(self) -> None:
        """Clock context should disambiguate location questions."""
        clock = orac_module.system_clock_line(
            {
                "timezone": "Europe/London",
                "weather_location": "Thornton Dale, England, United Kingdom",
            }
        )

        self.assertIn(
            "Assume your current location is Thornton Dale, England, United Kingdom.",
            clock,
        )
        self.assertIn(
            "This weather location is the preferred location context",
            clock,
        )
        self.assertIn(
            "If asked where you are, where you are located, or similar, answer "
            "with this configured operational/home location.",
            clock,
        )
        self.assertIn("physical embodiment", clock)
        self.assertNotIn("based on the session timezone", clock)

    def test_clock_context_disambiguates_inferred_location(self) -> None:
        """Clock context should also disambiguate timezone-derived location."""
        clock = orac_module.system_clock_line({"timezone": "Europe/London"})

        self.assertIn(
            "No explicit weather location is set. Assume your current location is London",
            clock,
        )
        self.assertIn(
            "If asked where you are, where you are located, or similar, answer "
            "with this inferred operational/home location.",
            clock,
        )
        self.assertIn("physical embodiment", clock)

    def test_system_primer_includes_creator_and_model_provenance_rules(self) -> None:
        """System primer should constrain creator and vendor provenance."""
        primer = orac_module._orac_system_primer(
            {"reply_language": "English"},
            {
                "title": "SYSTEM POLICY — ORAC PERSONA:",
                "identity": {
                    "assistant_name": "Orac",
                    "identity_answer_policy": (
                        "Configured identity policy for {assistant_name}: Only "
                        "answer with the identity statement when the user "
                        "explicitly asks who or what you are, who created you, "
                        "or another direct identity/creator question. For those "
                        "questions, answer simply: \"{identity_answer}.\" Do "
                        "not include {assistant_name}'s identity or creator in "
                        "replies to ordinary factual requests such as date, "
                        "time, weather, calculations, or status questions "
                        "unless the user asks for it."
                    ),
                    "disallowed_vendor_claims": [
                        "DeepSeek",
                        "OpenAI",
                        "Google",
                    ],
                    "creator_profile": {
                        "name": "Clive Bostock",
                        "role": "Orac's author and designer",
                        "notable_works": ["OraTAPI"],
                    },
                    "rules": [
                        "Treat the creator_profile facts as authoritative.",
                    ],
                },
            },
        )

        self.assertIn(
            "Configured identity policy for Orac: Only answer with the "
            "identity statement when the user explicitly asks who or what you "
            "are, who created you, or another direct identity/creator "
            "question.",
            primer,
        )
        self.assertIn(
            "For those questions, answer simply: \"I am Orac, an extensible "
            "artificial intelligence system, created by Clive Bostock.\"",
            primer,
        )
        self.assertIn(
            "Do not include Orac's identity or creator in replies to ordinary "
            "factual requests such as date, time, weather, calculations, or "
            "status questions unless the user asks for it.",
            primer,
        )
        self.assertIn(
            "Orac was created by Clive Bostock, Orac's author and designer.",
            primer,
        )
        self.assertIn(
            "Do not volunteer details about Orac's implementation, "
            "underlying model, runtime, training, or vendor provenance.",
            primer,
        )
        self.assertIn(
            "If asked whether Orac was created, trained, or operated by a "
            "third-party model vendor, answer no without listing vendor "
            "names.",
            primer,
        )
        self.assertIn(
            "Only if asked specifically about technical implementation "
            "details, say Orac is running on the configured local "
            "model/runtime.",
            primer,
        )
        self.assertIn(
            "do not add vendor denials to ordinary identity answers.",
            primer,
        )
        self.assertNotIn("Google", primer)
        self.assertNotIn("OpenAI", primer)
        self.assertNotIn("DeepSeek", primer)
        self.assertNotIn("assistant application", primer)
        self.assertNotIn("currently backed", primer)
        self.assertNotIn("large language model", primer)
        self.assertNotIn("LLM", primer)
        self.assertIn("Creator profile notable works: OraTAPI.", primer)
        self.assertIn(
            "Treat the creator_profile facts as authoritative.",
            primer,
        )

    def test_configured_policy_owns_identity_answer_policy_text(self) -> None:
        """System prompt YAML should own the identity answer policy wording."""
        policy = orac_module._load_system_prompt_policy(
            PROJECT_ROOT / "resources" / "config" / "orac_system_prompt.yaml"
        )

        identity_policy = policy["identity"]["identity_answer_policy"]

        self.assertIn("{assistant_name}", identity_policy)
        self.assertIn("{identity_answer}", identity_policy)
        self.assertIn("ordinary factual requests such as date", identity_policy)

    def setUp(self) -> None:
        self._original_logger = orac_module.logger
        self._original_validate_frame = orac_module.validate_frame
        orac_module.logger = _FakeLogger()
        orac_module.validate_frame = lambda env: None

    def tearDown(self) -> None:
        orac_module.logger = self._original_logger
        orac_module.validate_frame = self._original_validate_frame

    def _make_orac_stub(
        self,
        *,
        llm_responses: list[str],
        plugin_router=None,
        context_manager: _MemoryContextManager | None = None,
    ) -> Orac:
        orchestrator = Orac.__new__(Orac)
        orchestrator.model_name = "test-model"
        orchestrator.llm_service_id = "ollama"
        orchestrator.service_url = "http://localhost:11434"
        orchestrator._available_backend_models = {"test-model"}
        orchestrator._llm_connector_cache = {}
        orchestrator.enable_prompt_dump = False
        orchestrator._force_prompt_dump = False
        orchestrator._dump_context_flag = PROJECT_ROOT / ".orac-dump-context"
        orchestrator.strip_reasoning_tags = True
        orchestrator._history_turn_pairs = 24
        orchestrator._reply_language = "English"
        orchestrator._default_timezone = "Europe/London"
        orchestrator._retrieval_response_style = "normal"
        orchestrator._conversation_timeout_secs = 3600
        orchestrator._use_history = True
        orchestrator._economy_mode = "normal"
        orchestrator._archive_on_rollover = False
        orchestrator._close_on_rollover = True
        orchestrator._allow_external_session_id = False
        orchestrator._session_scope = "user"
        orchestrator._normalize_client = True
        orchestrator._history_budget_tokens = 1200
        orchestrator._history_budget_reserve = 300
        orchestrator._keep_messages = 200
        orchestrator._prune_after_turns = 50
        orchestrator._plugin_routing_enabled = False
        orchestrator._plugin_routing_ready = True
        orchestrator._plugin_routing_candidate_count = 3
        orchestrator._plugin_routing_min_score = None
        orchestrator.plugin_manager = None
        orchestrator.plugin_router = plugin_router
        orchestrator.retrieval_service = None
        orchestrator.retrieval_decision_service = RetrievalDecisionService(
            settings=RetrievalSettings(
                internet_search_enabled=True,
                internet_search_mode="explicit_only",
                default_search_provider="searxng",
                max_search_results=5,
                max_sources_to_fetch=3,
                cache_ttl_hours=1,
                require_citations=True,
            ),
            logger=orac_module.logger,
        )
        orchestrator._retrieval_context_by_session = {}
        orchestrator._pending_retrieval_by_session = {}
        orchestrator.config_mgr = object()
        orchestrator._system_prompt_policy = {
            "title": "SYSTEM POLICY — ORAC PERSONA:",
            "identity": {
                "assistant_name": "Orac",
                "disallowed_vendor_claims": [
                    "DeepSeek",
                    "OpenAI",
                    "Google",
                    "Anthropic",
                    "Meta",
                ],
                "creator_profile": {
                    "name": "Clive Bostock",
                    "role": "Orac's author and designer",
                    "notable_works": [
                        "CTk Theme Builder",
                        "CTkFontAwesome",
                        "OraTAPI",
                    ],
                },
                "rules": [
                    "Treat the creator_profile facts as authoritative.",
                ],
            },
            "response_style": {
                "rules": [
                    "Be concise, helpful, and neutral.",
                    "For follow-up turns, continue directly with the answer and do not add conversational openers such as 'Hello', 'Hi again', or 'You asked me to...'.",
                    "If the user's message is a reaction, observation, acknowledgement, or rhetorical remark rather than a factual question or task, respond to that reaction directly instead of repeating the previous answer.",
                ]
            },
            "language": {
                "rules": [
                    "Reply in {reply_language} unless the user's message is clearly in another language; in that case, reply in the user's language.",
                ]
            },
            "memory": {
                "rules": [
                    "The 'Recent exchange' below contains selected recent conversation history for this session.",
                    "Use recent exchange as private context only. Do not mention, label, summarise, or quote the words 'Recent exchange' in the reply unless the user explicitly asks about Orac's prompt or context.",
                    "You MUST use information the user has voluntarily shared in this conversation to answer their questions.",
                    "When asked about personal details (name, location, preferences, etc.), check the conversation history first.",
                    "If the user previously mentioned a fact in this conversation, reference it directly.",
                    "For ordinary factual questions, use your general knowledge as well as relevant context from the recent exchange.",
                    "Do not treat earlier assistant answers as authoritative if they conflict with reliable knowledge; correct materially wrong earlier answers plainly.",
                    "For personal or session-specific facts, only say you know them when they are present in authenticated context or the recent exchange.",
                    "When a user likely misspells or uses a variant of a well-known proper noun, state the likely interpretation and answer under that interpretation; ask for clarification only if multiple plausible meanings remain.",
                    "Treat elliptical follow-up prompts such as 'tell me more', 'go on', 'explain that', 'why?', and similar short continuations as referring to the immediately preceding assistant answer unless the user clearly changes topic.",
                    "For short or ambiguous follow-up questions such as 'who won', 'which one', 'how many', 'what about that', or 'what happened next', resolve the question against the immediately preceding user/assistant exchange unless the user clearly names a different topic. Do not answer an older unrelated topic merely because it appears in recent history.",
                    "When the user asks for more detail about the previous answer, expand it with new information rather than restating the same summary.",
                    "Do not repeat the previous factual answer unless the user explicitly asks for repetition, clarification, or more detail.",
                    "Do not add corrective asides such as 'in reality' unless the user asks for fact verification or the earlier answer was materially wrong.",
                ]
            },
            "profile_facts": {
                "rules": [
                    "Treat authenticated user facts as trusted session context.",
                    "If the user asks about a profile fact available in authenticated context, answer directly.",
                    "If the user provides a profile fact that matches authenticated context, acknowledge it naturally instead of acting surprised.",
                    "You may use the user's name naturally when helpful, but do not greet or re-greet the user in the middle of an ongoing conversation unless the user has just greeted you.",
                ]
            },
            "safety": {
                "rules": [
                    "Do not invoke privacy restrictions for information the user has already shared with you.",
                    "Do not invent facts or claim long-term memory beyond what is shown.",
                    "Do not include <think>…</think> or similar tags in your replies.",
                ]
            },
        }
        orchestrator.llm = _FakeLLM(llm_responses)
        orchestrator._get_llm_connector = lambda **kwargs: orchestrator.llm
        orchestrator.ctx = context_manager or _MemoryContextManager()
        orchestrator.auth_chain = _FakeAuthChain("clive")
        orchestrator._persistence_failures = []
        orchestrator._fail_on_persistence_error = False
        orchestrator._maybe_set_conversation_title = lambda *args, **kwargs: None
        orchestrator._maybe_prune = lambda session_id, last_turn_index: None
        return orchestrator

    @staticmethod
    def _request(
        prompt: str,
        *,
        req_id: str,
        meta: dict | None = None,
    ) -> str:
        return json.dumps(
            {
                "v": 1,
                "type": "request",
                "id": req_id,
                "ts": "2026-04-26T10:00:00Z",
                "route": "orac.prompt",
                "meta": {"client": "apex", **(meta or {})},
                "payload": {"messages": [{"role": "user", "content": prompt}]},
            },
            ensure_ascii=False,
        )

    def test_contextual_prompt_uses_configured_timezone_by_default(self) -> None:
        """Prompt context should use the configured runtime timezone."""
        orchestrator = self._make_orac_stub(llm_responses=[])
        orchestrator._default_timezone = "Europe/Paris"

        prompt = orchestrator._build_contextual_prompt(
            "session-1",
            "What time is it?",
            {},
            "clive",
        )

        self.assertIn("Session timezone preference: Europe/Paris.", prompt)
        self.assertIn("answer with the exact HH:MM value", prompt)

    def test_contextual_prompt_allows_request_timezone_override(self) -> None:
        """Request metadata may override the configured runtime timezone."""
        orchestrator = self._make_orac_stub(llm_responses=[])
        orchestrator._default_timezone = "Europe/Paris"

        prompt = orchestrator._build_contextual_prompt(
            "session-1",
            "What time is it?",
            {"timezone": "America/New_York"},
            "clive",
        )

        self.assertIn("Session timezone preference: America/New_York.", prompt)
        self.assertNotIn("Session timezone preference: Europe/Paris.", prompt)

    def test_contextual_prompt_tells_model_retrieval_already_happened(self) -> None:
        """Retrieved evidence should suppress generic no-internet disclaimers."""
        orchestrator = self._make_orac_stub(llm_responses=[])
        request = SearchRequest(
            query="Kevin Rowland latest single",
            trigger_phrase="search the internet for",
        )
        result = SearchResult(
            title="Kevin Rowland release",
            url="https://example.test/kevin-rowland",
            snippet="Release information.",
            source_name="example",
        )
        fetched = FetchedSource(
            url="https://example.test/kevin-rowland",
            title="Kevin Rowland release",
            source_name="example",
            text="Kevin Rowland released a new single according to this source.",
            excerpt="Kevin Rowland released a new single according to this source.",
        )
        retrieval_pack = GroundingPackBuilder().build(
            request,
            [result],
            [fetched],
            require_citations=True,
        )

        prompt = orchestrator._build_contextual_prompt(
            "session-1",
            "Search the internet for Kevin Rowland's latest single.",
            {},
            "clive",
            retrieval_pack=retrieval_pack,
        )

        self.assertIn("WEB RETRIEVAL EVIDENCE", prompt)
        self.assertIn("Orac has already retrieved", prompt)
        self.assertIn("Do not mention internal retrieval mechanics", prompt)
        self.assertIn("cite the source URLs", prompt)

    def test_contextual_prompt_suppresses_identity_for_date_questions(self) -> None:
        """Date questions should not invite the standard Orac identity answer."""
        orchestrator = self._make_orac_stub(llm_responses=[])

        prompt = orchestrator._build_contextual_prompt(
            "session-1",
            "Wjat is today's date?",
            {},
            "clive",
        )

        self.assertIn(
            "Do not include Orac's identity or creator in replies to ordinary "
            "factual requests such as date, time, weather, calculations, or "
            "status questions unless the user asks for it.",
            prompt,
        )
        self.assertIn(
            "When answering questions about the current time or date, use the "
            "user-facing local time above, not UTC.",
            prompt,
        )
        self.assertIn("Current user message:\n\nWjat is today's date?", prompt)

    def test_contextual_prompt_prefers_weather_location_over_timezone_location(
        self,
    ) -> None:
        """Weather location should outrank timezone-derived location."""
        orchestrator = self._make_orac_stub(llm_responses=[])
        orchestrator._default_timezone = "Europe/Paris"

        prompt = orchestrator._build_contextual_prompt(
            "session-1",
            "Where are you?",
            {
                "timezone": "America/New_York",
                "weather_location": "Thornton Dale, England, United Kingdom",
            },
            "clive",
        )

        self.assertIn(
            "Assume your current location is Thornton Dale, England, United Kingdom.",
            prompt,
        )
        self.assertIn(
            "This weather location is the preferred location context",
            prompt,
        )
        self.assertNotIn("Assume your current location is New York", prompt)
        self.assertNotIn("based on the session timezone", prompt)

    async def test_two_normal_turns_replay_first_turn_in_second_prompt(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Hello Clive.", "You asked earlier whether I remembered that."],
        )

        await orchestrator.handle_request(self._request("Hello, Orac.", req_id="req1"))
        await orchestrator.handle_request(self._request("What did I just say?", req_id="req2"))

        self.assertEqual(len(orchestrator.llm.prompts), 2)
        second_prompt = orchestrator.llm.prompts[1]
        self.assertIn("USER: Hello, Orac.", second_prompt)
        self.assertIn("ASSISTANT: Hello Clive.", second_prompt)

    async def test_follow_up_prompt_includes_elliptical_reference_rules(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=[
                "The Battle of Agincourt was fought in 1415.",
                "Agincourt also reflected French command problems.",
            ],
        )

        await orchestrator.handle_request(
            self._request("What was the battle of Agincourt?", req_id="req1")
        )
        await orchestrator.handle_request(
            self._request("Tell me more", req_id="req2")
        )

        self.assertEqual(len(orchestrator.llm.prompts), 2)
        follow_up_prompt = orchestrator.llm.prompts[1]
        self.assertIn(
            "Treat elliptical follow-up prompts such as 'tell me more', "
            "'go on', 'explain that', 'why?', and similar short "
            "continuations as referring to the immediately preceding "
            "assistant answer unless the user clearly changes topic.",
            follow_up_prompt,
        )
        self.assertIn(
            "For short or ambiguous follow-up questions such as 'who won', "
            "'which one', 'how many', 'what about that', or 'what happened "
            "next', resolve the question against the immediately preceding "
            "user/assistant exchange unless the user clearly names a "
            "different topic.",
            follow_up_prompt,
        )
        self.assertIn(
            "If the current message is a short or ambiguous follow-up, "
            "resolve it against the immediately preceding user/assistant "
            "exchange rather than an older unrelated topic.",
            follow_up_prompt,
        )
        self.assertIn(
            "Use recent exchange as private context only. Do not mention, "
            "label, summarise, or quote the words 'Recent exchange' in the "
            "reply unless the user explicitly asks about Orac's prompt or "
            "context.",
            follow_up_prompt,
        )
        self.assertIn(
            "When the user asks for more detail about the previous answer, "
            "expand it with new information rather than restating the same "
            "summary.",
            follow_up_prompt,
        )
        self.assertIn("USER: What was the battle of Agincourt?", follow_up_prompt)
        self.assertIn(
            "ASSISTANT: The Battle of Agincourt was fought in 1415.",
            follow_up_prompt,
        )
        self.assertIn("Current user message:\n\nTell me more", follow_up_prompt)

    async def test_follow_up_prompt_discourages_regreeting_mid_conversation(
        self,
    ) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=[
                "Agincourt was a major English victory.",
                "It also weakened French noble leadership.",
            ],
        )

        await orchestrator.handle_request(
            self._request("What was the battle of Agincourt?", req_id="req1")
        )
        await orchestrator.handle_request(
            self._request("Tell me more.", req_id="req2")
        )

        follow_up_prompt = orchestrator.llm.prompts[1]
        self.assertIn(
            "For follow-up turns, continue directly with the answer and do "
            "not add conversational openers such as 'Hello', 'Hi again', or "
            "'You asked me to...'.",
            follow_up_prompt,
        )
        self.assertIn(
            "You may use the user's name naturally when helpful, but do not "
            "greet or re-greet the user in the middle of an ongoing "
            "conversation unless the user has just greeted you.",
            follow_up_prompt,
        )

    async def test_follow_up_prompt_discourages_corrective_asides(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Short answer."],
        )

        await orchestrator.handle_request(
            self._request("Explain this briefly.", req_id="req1")
        )

        prompt = orchestrator.llm.prompts[0]
        self.assertIn(
            "Do not add corrective asides such as 'in reality' unless the "
            "user asks for fact verification or the earlier answer was "
            "materially wrong.",
            prompt,
        )
        self.assertNotIn("If you wish, you may add one brief 'In reality", prompt)

    async def test_follow_up_prompt_allows_general_knowledge_correction(
        self,
    ) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=[
                "The Battle of Ajincourt was a naval engagement in 1744.",
                "Henry won through terrain, longbows, and French disorder.",
            ],
        )

        await orchestrator.handle_request(
            self._request("What was the battle of Ajincourt?", req_id="req1")
        )
        await orchestrator.handle_request(
            self._request("How did king Henry manage to win?", req_id="req2")
        )

        self.assertEqual(len(orchestrator.llm.prompts), 2)
        follow_up_prompt = orchestrator.llm.prompts[1]
        self.assertIn("USER: What was the battle of Ajincourt?", follow_up_prompt)
        self.assertIn(
            "ASSISTANT: The Battle of Ajincourt was a naval engagement in 1744.",
            follow_up_prompt,
        )
        self.assertIn(
            "Current user message:\n\nHow did king Henry manage to win?",
            follow_up_prompt,
        )
        self.assertIn(
            "For ordinary factual questions, use your general knowledge as "
            "well as relevant context.",
            follow_up_prompt,
        )
        self.assertIn(
            "Do not treat earlier assistant answers as authoritative if "
            "they conflict with reliable knowledge; correct materially "
            "wrong earlier answers plainly.",
            follow_up_prompt,
        )
        self.assertIn(
            "If a proper noun appears misspelled or variant, state the "
            "likely interpretation and answer under that interpretation",
            follow_up_prompt,
        )

    async def test_reaction_turn_prompt_discourages_repeating_previous_answer(
        self,
    ) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=[
                "Many French nobles were killed.",
                "It does seem remarkable given the disparity in losses.",
            ],
        )

        await orchestrator.handle_request(
            self._request("What were the estimated casualties?", req_id="req1")
        )
        await orchestrator.handle_request(
            self._request("Tis a miracle.", req_id="req2")
        )

        reaction_prompt = orchestrator.llm.prompts[1]
        self.assertIn(
            "If the user's message is a reaction, observation, "
            "acknowledgement, or rhetorical remark rather than a factual "
            "question or task, respond to that reaction directly instead of "
            "repeating the previous answer.",
            reaction_prompt,
        )
        self.assertIn(
            "Do not repeat the previous factual answer unless the user "
            "explicitly asks for repetition, clarification, or more detail.",
            reaction_prompt,
        )
        self.assertIn("Current user message:\n\nTis a miracle.", reaction_prompt)

    async def test_authenticated_user_profile_is_injected_into_prompt(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Your name is Clive."],
        )

        await orchestrator.handle_request(self._request("What is my name?", req_id="req-profile"))

        self.assertEqual(len(orchestrator.llm.prompts), 1)
        prompt = orchestrator.llm.prompts[0]
        self.assertIn("Known user facts:", prompt)
        self.assertIn("Authenticated username: clive", prompt)
        self.assertIn("Display name: Clive", prompt)

    async def test_streaming_turn_persists_final_usage_metadata(self) -> None:
        context_manager = _MemoryContextManager()
        orchestrator = self._make_orac_stub(
            llm_responses=["Streaming answer."],
            context_manager=context_manager,
        )
        orchestrator.llm.stream_usage_metadata = LLMUsageMetadata(
            prompt_tokens=13,
            completion_tokens=8,
            total_tokens=21,
            raw={"prompt_eval_count": 13, "eval_count": 8},
        )

        stream_events: list[dict] = []

        async def _event_sink(event: dict) -> None:
            stream_events.append(event)

        await orchestrator.handle_request(
            self._request(
                "Stream this answer.",
                req_id="req-stream-usage",
                meta={"stream": True},
            ),
            event_sink=_event_sink,
        )

        assistant_rows = [
            row
            for row in context_manager.messages_by_session["clive"]
            if row["role"] == "assistant"
        ]
        self.assertEqual(len(assistant_rows), 1)
        self.assertEqual(assistant_rows[0]["tokens_used"], 21)
        self.assertTrue(
            any(event.get("type") == "text_delta" for event in stream_events)
        )

    async def test_plugin_handled_turn_is_persisted_and_replayed_into_next_prompt(self) -> None:
        plugin_content = "In Brigadoon, Khomas Region, Namibia, it's currently 21°C and clear."
        orchestrator = self._make_orac_stub(
            llm_responses=["Yes, Brigadoon is a real place name used in Namibia."],
            plugin_router=_ConditionalPluginRouter(plugin_content),
        )

        first_wire = await orchestrator.handle_request(
            self._request("What is the weather like in Brigadoon?", req_id="req1")
        )
        second_wire = await orchestrator.handle_request(
            self._request("There is actually a place called Brigadoon?", req_id="req2")
        )

        first_response = json.loads(first_wire)
        second_response = json.loads(second_wire)

        self.assertEqual(first_response["meta"]["status"], "ok")
        self.assertEqual(second_response["meta"]["status"], "ok")
        self.assertEqual(len(orchestrator.llm.prompts), 1)
        second_prompt = orchestrator.llm.prompts[0]
        self.assertIn(plugin_content, second_prompt)
        self.assertIn("USER: What is the weather like in Brigadoon?", second_prompt)

    async def test_same_authenticated_user_reuses_same_open_conversation_within_timeout(self) -> None:
        context_manager = _MemoryContextManager()
        orchestrator = self._make_orac_stub(
            llm_responses=["First answer.", "Second answer."],
            context_manager=context_manager,
        )

        await orchestrator.handle_request(self._request("First prompt", req_id="req1"))
        await orchestrator.handle_request(self._request("Second prompt", req_id="req2"))

        user_turn_sessions = [
            session_id
            for session_id, role, _text in context_manager.saved_events
            if role == "user"
        ]
        self.assertEqual(user_turn_sessions, ["clive", "clive"])
        self.assertEqual(len(context_manager.conversation_ids), 1)
        self.assertEqual(context_manager.ensure_calls[0][2], context_manager.ensure_calls[1][2])
        self.assertTrue(
            context_manager.get_conversation_prompt_policy_fingerprint("clive")
        )

    async def test_default_generation_options_stay_on_system_defaults(self) -> None:
        context_manager = _MemoryContextManager()
        orchestrator = self._make_orac_stub(
            llm_responses=["Default preset answer."],
            context_manager=context_manager,
        )

        await orchestrator.handle_request(
            self._request("Use the default style.", req_id="req-default")
        )

        self.assertEqual(
            orchestrator.llm.generation_options_seen[-1],
            {
                "temperature": 0.2,
                "repeat_penalty": 1.1,
            },
        )

    async def test_persona_model_preset_drives_generation_options(self) -> None:
        context_manager = _MemoryContextManager()
        context_manager.personalities["DEFAULT"] = {
            "PERSONALITY_CODE": "DEFAULT",
            "PERSONALITY_NAME": "Default",
            "MODEL_PRESET_ID": 2,
        }
        context_manager.model_generation_presets[2] = {
            "MODEL_PRESET_ID": 2,
            "MODEL_PRESET_CODE": "PRECISE_DETAILED",
            "TEMPERATURE": 0.15,
            "TOP_P": 0.9,
            "TOP_K": 40,
            "REPEAT_PENALTY": 1.1,
            "NUM_PREDICT": 3072,
            "SEED": None,
        }
        orchestrator = self._make_orac_stub(
            llm_responses=["Preset answer."],
            context_manager=context_manager,
        )

        await orchestrator.handle_request(
            self._request("Use the persona preset.", req_id="req-preset")
        )

        self.assertEqual(
            orchestrator.llm.generation_options_seen[-1],
            {
                "temperature": 0.15,
                "repeat_penalty": 1.1,
                "top_p": 0.9,
                "top_k": 40,
                "num_predict": 3072,
            },
        )

    async def test_persona_model_preset_overrides_selected_default_preset(self) -> None:
        context_manager = _MemoryContextManager()
        context_manager.personalities["DEFAULT"] = {
            "PERSONALITY_CODE": "DEFAULT",
            "PERSONALITY_NAME": "Default",
            "MODEL_PRESET_ID": 2,
        }
        context_manager.model_generation_presets[1] = {
            "MODEL_PRESET_ID": 1,
            "MODEL_PRESET_CODE": "CREATIVE",
            "TEMPERATURE": 0.75,
            "NUM_PREDICT": 2048,
        }
        context_manager.model_generation_presets[2] = {
            "MODEL_PRESET_ID": 2,
            "MODEL_PRESET_CODE": "PRECISE",
            "TEMPERATURE": 0.1,
            "NUM_PREDICT": 1536,
        }
        orchestrator = self._make_orac_stub(
            llm_responses=["Preset precedence answer."],
            context_manager=context_manager,
        )

        await orchestrator.handle_request(
            self._request(
                "Use the persona preset.",
                req_id="req-preset-precedence",
                meta={"model_preset_id": 1},
            )
        )

        self.assertEqual(
            orchestrator.llm.generation_options_seen[-1],
            {
                "temperature": 0.1,
                "repeat_penalty": 1.1,
                "num_predict": 1536,
            },
        )

    async def test_force_new_conversation_meta_starts_new_conversation(self) -> None:
        context_manager = _MemoryContextManager()
        orchestrator = self._make_orac_stub(
            llm_responses=["First answer.", "Fresh answer."],
            context_manager=context_manager,
        )

        await orchestrator.handle_request(self._request("First prompt", req_id="req1"))
        await orchestrator.handle_request(
            self._request(
                "Fresh prompt",
                req_id="req2",
                meta={"force_new_conversation": True},
            )
        )

        user_turn_sessions = [
            session_id
            for session_id, role, _text in context_manager.saved_events
            if role == "user"
        ]
        self.assertEqual(context_manager.closed_sessions, ["clive"])
        self.assertEqual(user_turn_sessions[0], "clive")
        self.assertTrue(user_turn_sessions[1].startswith("clive#"))
        fresh_user_meta = context_manager.messages_by_session[
            user_turn_sessions[1]
        ][1]["meta"]
        self.assertNotIn("force_new_conversation", fresh_user_meta)

    async def test_prompt_policy_fingerprint_change_starts_new_conversation(
        self,
    ) -> None:
        context_manager = _MemoryContextManager()
        orchestrator = self._make_orac_stub(
            llm_responses=["First answer.", "Fresh policy answer."],
            context_manager=context_manager,
        )

        await orchestrator.handle_request(self._request("First prompt", req_id="req1"))
        old_fingerprint = (
            context_manager.get_conversation_prompt_policy_fingerprint("clive")
        )
        orchestrator._system_prompt_policy["safety"]["rules"].append(
            "New policy rule for test isolation."
        )
        await orchestrator.handle_request(
            self._request("Second prompt", req_id="req2")
        )

        user_turn_sessions = [
            session_id
            for session_id, role, _text in context_manager.saved_events
            if role == "user"
        ]
        self.assertEqual(context_manager.closed_sessions, ["clive"])
        self.assertEqual(user_turn_sessions[0], "clive")
        self.assertTrue(user_turn_sessions[1].startswith("clive#"))
        new_fingerprint = (
            context_manager.get_conversation_prompt_policy_fingerprint(
                user_turn_sessions[1]
            )
        )
        self.assertNotEqual(old_fingerprint, new_fingerprint)

    async def test_default_llm_preference_change_starts_new_conversation(self) -> None:
        context_manager = _MemoryContextManager()
        context_manager.conversation_ids["clive"] = 1
        context_manager.conversation_llm_ids["clive"] = 1
        context_manager.messages_by_session["clive"] = []
        context_manager.user_preferences[("clive", "default_llm_id")] = "2"
        context_manager.llm_registry_entries[2] = {
            "LLM_ID": 2,
            "PROVIDER": "ollama",
            "MODEL": "preferred-model",
            "IS_ENABLED": "Y",
        }
        orchestrator = self._make_orac_stub(
            llm_responses=["Using preferred model."],
            context_manager=context_manager,
        )
        orchestrator._available_backend_models = {"test-model", "preferred-model"}

        wire = await orchestrator.handle_request(
            self._request("Use my selected model.", req_id="req-llm-pref")
        )
        response = json.loads(wire)
        user_turn_sessions = [
            session_id
            for session_id, role, _text in context_manager.saved_events
            if role == "user"
        ]

        self.assertEqual(response["meta"]["model"], "preferred-model")
        self.assertEqual(response["meta"]["personality_code"], "DEFAULT")
        self.assertEqual(response["meta"]["llm_source"], "user_preference")
        self.assertEqual(context_manager.closed_sessions, ["clive"])
        self.assertEqual(len(user_turn_sessions), 1)
        self.assertTrue(user_turn_sessions[0].startswith("clive#"))
        self.assertEqual(
            context_manager.conversation_llm_ids[user_turn_sessions[0]],
            2,
        )

    async def test_missing_default_llm_preference_uses_configured_default(self) -> None:
        context_manager = _MemoryContextManager()
        context_manager.conversation_ids["clive"] = 1
        context_manager.conversation_llm_ids["clive"] = None
        context_manager.messages_by_session["clive"] = []
        orchestrator = self._make_orac_stub(
            llm_responses=["Configured default answer."],
            context_manager=context_manager,
        )

        wire = await orchestrator.handle_request(
            self._request("Use the configured model.", req_id="req-default")
        )
        response = json.loads(wire)

        self.assertEqual(response["meta"]["model"], "test-model")
        self.assertEqual(response["meta"]["llm_source"], "configured_default")

    async def test_unavailable_default_llm_preference_falls_back_with_warning_source(
        self,
    ) -> None:
        context_manager = _MemoryContextManager()
        context_manager.user_preferences[("clive", "default_llm_id")] = "2"
        context_manager.llm_registry_entries[2] = {
            "LLM_ID": 2,
            "PROVIDER": "ollama",
            "MODEL": "preferred-model",
            "IS_ENABLED": "Y",
        }
        orchestrator = self._make_orac_stub(
            llm_responses=["Fallback answer."],
            context_manager=context_manager,
        )
        orchestrator._available_backend_models = {"test-model"}
        context_manager.ensure_conversation_with_timeout = (
            lambda *, user_name, session_id_base, llm_id, timeout_seconds: {
                "conversation_id": 7,
                "session_id": f"{session_id_base}#fresh",
                "rolled_over": True,
                "age_seconds": 7200.0,
                "previous_conversation_id": 6,
                "previous_session_id": session_id_base,
            }
        )

        wire = await orchestrator.handle_request(
            self._request("Use my preferred model.", req_id="req-fallback")
        )
        response = json.loads(wire)

        self.assertEqual(response["meta"]["model"], "test-model")
        self.assertEqual(response["meta"]["llm_source"], "configured_fallback")

    async def test_explicit_retrieval_failure_returns_clear_answer_without_llm(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Ungrounded current facts."],
        )
        retrieval_service = _UnavailableRetrievalService(
            "I could not retrieve online evidence for that request."
        )
        orchestrator.retrieval_service = retrieval_service

        wire = await orchestrator.handle_request(
            self._request("search the web for latest Orac news", req_id="req-search")
        )
        response = json.loads(wire)

        self.assertEqual(
            response["payload"]["content"],
            "I could not retrieve online evidence for that request.",
        )
        self.assertEqual(orchestrator.llm.prompts, [])
        self.assertEqual(retrieval_service.prompts, ["search the web for latest Orac news"])

    async def test_person_death_retrieval_failure_does_not_fall_back_to_stale_llm(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Kelly Curtis died in 2009."],
        )
        orchestrator.retrieval_decision_service = RetrievalDecisionService(
            settings=RetrievalSettings(
                internet_search_enabled=True,
                internet_search_mode="explicit_only",
                default_search_provider="searxng",
                max_search_results=5,
                max_sources_to_fetch=3,
                cache_ttl_hours=1,
                require_citations=True,
            ),
            logger=orac_module.logger,
        )
        retrieval_service = _UnavailableRetrievalService(
            "I found results, but they did not appear relevant enough to verify that safely."
        )
        orchestrator.retrieval_service = retrieval_service

        wire = await orchestrator.handle_request(
            self._request("When did Kelly Curtis die?", req_id="req-kelly-death")
        )
        response = json.loads(wire)

        content = response["payload"]["content"]
        self.assertEqual(
            content,
            "I found results, but they did not appear relevant enough to verify that safely.",
        )
        self.assertEqual(orchestrator.llm.prompts, [])
        self.assertNotIn("2009", content)
        self.assertNotIn("reason_code", content)
        self.assertNotIn("RetrievalDecisionService", content)
        self.assertNotIn("grounding pack", content.lower())

    async def test_person_death_disabled_mode_returns_verification_disabled_message(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Kelly Curtis died in 2009."],
        )
        orchestrator.retrieval_decision_service = RetrievalDecisionService(
            settings=RetrievalSettings(
                internet_search_enabled=True,
                internet_search_mode="disabled",
                default_search_provider="searxng",
                max_search_results=5,
                max_sources_to_fetch=3,
                cache_ttl_hours=1,
                require_citations=True,
            ),
            logger=orac_module.logger,
        )
        retrieval_service = _UnavailableRetrievalService("Retrieval should not run.")
        orchestrator.retrieval_service = retrieval_service

        wire = await orchestrator.handle_request(
            self._request("When did Kelly Curtis die?", req_id="req-kelly-disabled")
        )
        response = json.loads(wire)

        content = response["payload"]["content"]
        self.assertIn("Internet retrieval is disabled", content)
        self.assertIn("current information cannot be verified", content)
        self.assertEqual(orchestrator.llm.prompts, [])
        self.assertEqual(retrieval_service.prompts, [])
        self.assertNotIn("2009", content)

    async def test_stable_person_age_answer_does_not_use_llm(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Bing Crosby is 123."],
        )

        wire = await orchestrator.handle_request(
            self._request("How old is Bing Crosby?", req_id="req-bing-age")
        )
        response = json.loads(wire)

        content = response["payload"]["content"]
        self.assertIn("Bing Crosby was 74 when he died", content)
        self.assertIn("3 May 1903", content)
        self.assertIn("14 October 1977", content)
        self.assertIn("would be 123", content)
        self.assertEqual(orchestrator.llm.prompts, [])

    async def test_explicit_retrieval_success_keeps_response_natural(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=[
                (
                    "The song is 'My Life in England, Pt. 1' by Dexys Midnight Runners. "
                    "The retrieved evidence confirms its existence and availability on platforms like "
                    "YouTube and Spotify, though the specific lyrics or full track details were not "
                    "fully extracted in the search results."
                )
            ],
        )
        request = SearchRequest(
            query="Kevin Rowland latest single",
            trigger_phrase="search the internet for",
        )
        pack = GroundingPackBuilder().build(
            request,
            [SearchResult(title="Dexys Midnight Runners", url="https://example.test/song")],
            [
                FetchedSource(
                    url="https://example.test/song",
                    title="Dexys Midnight Runners",
                    source_name="example.test",
                    text="My Life in England, Pt. 1 is a song by Dexys Midnight Runners.",
                    excerpt="My Life in England, Pt. 1 is a song by Dexys Midnight Runners.",
                )
            ],
            require_citations=True,
        )
        retrieval_service = _SuccessfulRetrievalService(pack)
        orchestrator.retrieval_service = retrieval_service

        wire = await orchestrator.handle_request(
            self._request("search the internet for Kevin Rowland's latest single", req_id="req-search")
        )
        response = json.loads(wire)
        content = response["payload"]["content"]

        self.assertEqual(content, "The song is 'My Life in England, Pt. 1' by Dexys Midnight Runners.")
        self.assertNotIn("retrieved evidence", content.lower())
        self.assertNotIn("grounding pack", content.lower())
        self.assertNotIn("fetched sources", content.lower())
        self.assertNotIn("search results confirm", content.lower())
        self.assertNotIn("reason_code", content.lower())
        self.assertNotIn("retrievaldecisionservice", content.lower())
        self.assertEqual(
            retrieval_service.prompts,
            ["search the internet for Kevin Rowland's latest single"],
        )

    async def test_streaming_retrieval_emits_lifecycle_events_before_answer(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Oracle Database 23ai is the current release."],
        )
        request = SearchRequest(
            query="What is the latest version of the Oracle Database?",
            trigger_phrase="what is the latest",
        )
        pack = GroundingPackBuilder().build(
            request,
            [
                SearchResult(
                    title="Oracle Database",
                    url="https://example.test/oracle-db",
                )
            ],
            [
                FetchedSource(
                    url="https://example.test/oracle-db",
                    title="Oracle Database",
                    source_name="example.test",
                    text="Oracle Database 23ai is the current release.",
                    excerpt="Oracle Database 23ai is the current release.",
                )
            ],
            require_citations=True,
        )
        orchestrator.retrieval_service = _SuccessfulRetrievalService(pack)

        stream_frames: list[dict[str, object]] = []

        async def _event_sink(event: dict[str, object]) -> None:
            stream_frames.append(dict(event))

        wire = await orchestrator.handle_request(
            self._request(
                "What is the latest version of the Oracle Database?",
                req_id="req-oracle-db",
                meta={"stream": True},
            ),
            event_sink=_event_sink,
        )
        response = json.loads(wire)

        self.assertEqual(response["meta"]["status"], "ok")
        self.assertEqual(
            [frame["type"] for frame in stream_frames[:5]],
            [
                "retrieval_start",
                "retrieval_query",
                "retrieval_fetch_start",
                "retrieval_fetch_complete",
                "retrieval_complete",
            ],
        )
        self.assertEqual(stream_frames[0]["payload"]["mode"], "internet")
        self.assertEqual(stream_frames[1]["payload"]["provider"], "searxng")
        self.assertEqual(
            stream_frames[1]["payload"]["query"],
            "What is the latest version of the Oracle Database?",
        )
        self.assertIn("stream_start", [frame["type"] for frame in stream_frames])
        self.assertIn("stream_end", [frame["type"] for frame in stream_frames])
        self.assertEqual(len(orchestrator.llm.prompts), 1)
        self.assertIn("Current user message:", orchestrator.llm.prompts[0])
        self.assertIn("What is the latest version of the Oracle Database?", orchestrator.llm.prompts[0])

    async def test_streaming_retrieval_failure_emits_failed_event(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Fallback answer should not be used."],
        )
        orchestrator.retrieval_service = _UnavailableRetrievalService(
            "I could not retrieve online evidence for that request."
        )

        stream_frames: list[dict[str, object]] = []

        async def _event_sink(event: dict[str, object]) -> None:
            stream_frames.append(dict(event))

        wire = await orchestrator.handle_request(
            self._request(
                "What is the latest news on the war in Iran?",
                req_id="req-news-fail",
                meta={"stream": True},
            ),
            event_sink=_event_sink,
        )
        response = json.loads(wire)

        self.assertEqual(
            response["payload"]["content"],
            "I could not retrieve online evidence for that request.",
        )
        self.assertIn("retrieval_failed", [frame["type"] for frame in stream_frames])
        self.assertNotIn("retrieval_complete", [frame["type"] for frame in stream_frames])

    async def test_streaming_disabled_retrieval_emits_skipped_event(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Disabled retrieval answer."],
        )
        orchestrator.retrieval_decision_service = _StaticRetrievalDecisionService(
            RetrievalDecision(
                should_retrieve=False,
                retrieval_type="internet",
                confidence="high",
                reason_code="disabled",
                user_visible_reason="Internet retrieval is disabled right now, so current information cannot be verified.",
                explicit_request=True,
                requires_user_confirmation=False,
                search_query="latest news on the war in Iran",
            )
        )

        stream_frames: list[dict[str, object]] = []

        async def _event_sink(event: dict[str, object]) -> None:
            stream_frames.append(dict(event))

        wire = await orchestrator.handle_request(
            self._request(
                "What is the latest news on the war in Iran?",
                req_id="req-news-disabled",
                meta={"stream": True},
            ),
            event_sink=_event_sink,
        )
        response = json.loads(wire)

        self.assertEqual(
            response["payload"]["content"],
            "Internet retrieval is disabled right now, so current information cannot be verified.",
        )
        self.assertEqual(stream_frames[0]["type"], "retrieval_skipped")
        self.assertEqual(stream_frames[0]["payload"]["reason"], "retrieval_disabled")
        self.assertNotIn("retrieval_start", [frame["type"] for frame in stream_frames])

    async def test_streaming_local_answers_do_not_emit_retrieval_events(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Orac is structured around controller, model, and runtime services."],
        )

        stream_frames: list[dict[str, object]] = []

        async def _event_sink(event: dict[str, object]) -> None:
            stream_frames.append(dict(event))

        wire = await orchestrator.handle_request(
            self._request(
                "Explain the Orac architecture.",
                req_id="req-local-stream",
                meta={"stream": True},
            ),
            event_sink=_event_sink,
        )
        response = json.loads(wire)

        self.assertEqual(response["meta"]["status"], "ok")
        self.assertFalse(
            any(str(frame.get("type", "")).startswith("retrieval_") for frame in stream_frames)
        )
        frame_types = [frame["type"] for frame in stream_frames]
        self.assertEqual(frame_types[0], "stream_start")
        self.assertIn("text_delta", frame_types)
        self.assertIn("stream_end", frame_types)

    async def test_retrieval_follow_up_reuses_previous_context(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=[
                "The latest reports say the situation remains fluid.",
                "Yes. The latest reports add that the situation remains fluid.",
            ],
        )
        request = SearchRequest(
            query="latest news on Iran",
            trigger_phrase="search the internet for",
        )
        pack = GroundingPackBuilder().build(
            request,
            [SearchResult(title="Iran update", url="https://example.test/iran")],
            [
                FetchedSource(
                    url="https://example.test/iran",
                    title="Iran update",
                    source_name="example.test",
                    text="Iran-related reports remain fluid.",
                    excerpt="Iran-related reports remain fluid.",
                )
            ],
            require_citations=True,
        )
        retrieval_service = _SuccessfulRetrievalService(pack)
        orchestrator.retrieval_service = retrieval_service

        first_wire = await orchestrator.handle_request(
            self._request("What is the latest news on Iran?", req_id="req-news-1")
        )
        first_response = json.loads(first_wire)
        self.assertIn("The latest reports say", first_response["payload"]["content"])

        second_wire = await orchestrator.handle_request(
            self._request("Is there any more detail on that in the latest news?", req_id="req-news-2")
        )
        second_response = json.loads(second_wire)

        self.assertIn("The latest reports add", second_response["payload"]["content"])
        self.assertNotIn("did not explicitly request internet retrieval", second_response["payload"]["content"].lower())
        self.assertGreaterEqual(len(retrieval_service.prompts), 2)
        self.assertEqual(retrieval_service.prompts[0], "What is the latest news on Iran?")
        self.assertEqual(retrieval_service.prompts[1], "Iran")
        self.assertIn("clive", orchestrator._retrieval_context_by_session)

    async def test_retrieval_topic_pivot_starts_fresh_context(self) -> None:
        orchestrator = self._make_orac_stub(llm_responses=[])
        orchestrator.llm = _TopicSensitiveLLM()
        orchestrator._get_llm_connector = lambda **kwargs: orchestrator.llm

        def _pack(topic: str, query: str, url: str, excerpt: str) -> GroundingPack:
            return GroundingPackBuilder().build(
                SearchRequest(query=query, trigger_phrase="search the internet for"),
                [SearchResult(title=topic, url=url)],
                [
                    FetchedSource(
                        url=url,
                        title=topic,
                        source_name=url.split("//", 1)[-1].split("/", 1)[0],
                        text=excerpt,
                        excerpt=excerpt,
                    )
                ],
                require_citations=True,
            )

        retrieval_service = _TopicAwareRetrievalService(
            {
                "iran": _pack(
                    "Iran update",
                    "latest news on Iran",
                    "https://example.test/iran",
                    "Iran-related reports remain fluid.",
                ),
                "ukraine": _pack(
                    "Ukraine update",
                    "latest Ukraine-Russia war news",
                    "https://example.test/ukraine",
                    "Ukraine and Russia remain in active conflict.",
                ),
            }
        )
        orchestrator.retrieval_service = retrieval_service

        first_wire = await orchestrator.handle_request(
            self._request("What is the latest news on Iran?", req_id="req-iran")
        )
        first_response = json.loads(first_wire)
        self.assertIn("Iran-focused latest news answer.", first_response["payload"]["content"])

        second_wire = await orchestrator.handle_request(
            self._request("What's the latest on the Ukraine-Russia war?", req_id="req-ukraine")
        )
        second_response = json.loads(second_wire)

        self.assertIn("Ukraine-focused latest news answer.", second_response["payload"]["content"])
        self.assertNotIn("Iran-focused latest news answer.", second_response["payload"]["content"])
        self.assertGreaterEqual(len(retrieval_service.prompts), 2)
        self.assertNotIn("Iran", retrieval_service.prompts[1])
        self.assertIn("Ukraine", retrieval_service.prompts[1])
        context = orchestrator._retrieval_context_by_session["clive"]
        self.assertIn("ukraine", " ".join(context.topic_signature).lower())
        self.assertNotIn("iran", " ".join(context.topic_signature).lower())

    async def test_local_follow_up_does_not_trigger_internet_retrieval(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=[
                "Orac is structured around controller, model, and runtime services.",
                "The same core flow still applies here.",
            ],
        )
        retrieval_service = _UnavailableRetrievalService(
            "Internet retrieval should not run for local context."
        )
        orchestrator.retrieval_service = retrieval_service

        first_wire = await orchestrator.handle_request(
            self._request("Explain the Orac architecture", req_id="req-local-1")
        )
        first_response = json.loads(first_wire)
        self.assertIn("Orac is structured around controller", first_response["payload"]["content"])

        second_wire = await orchestrator.handle_request(
            self._request("tell me more about that", req_id="req-local-2")
        )
        second_response = json.loads(second_wire)

        self.assertIn("The same core flow", second_response["payload"]["content"])
        self.assertEqual(retrieval_service.prompts, [])
        self.assertNotIn(
            "did not explicitly request internet retrieval",
            second_response["payload"]["content"].lower(),
        )
        self.assertNotIn("retrievaldecisionservice", second_response["payload"]["content"].lower())

    async def test_disabled_follow_up_returns_natural_disabled_message(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=[
                "The latest reports say the situation remains fluid.",
                "Fallback answer should not be used.",
            ],
        )
        request = SearchRequest(
            query="latest news on Iran",
            trigger_phrase="search the internet for",
        )
        pack = GroundingPackBuilder().build(
            request,
            [SearchResult(title="Iran update", url="https://example.test/iran")],
            [
                FetchedSource(
                    url="https://example.test/iran",
                    title="Iran update",
                    source_name="example.test",
                    text="Iran-related reports remain fluid.",
                    excerpt="Iran-related reports remain fluid.",
                )
            ],
            require_citations=True,
        )
        orchestrator.retrieval_service = _SuccessfulRetrievalService(pack)

        await orchestrator.handle_request(
            self._request("What is the latest news on Iran?", req_id="req-news-1")
        )
        orchestrator.retrieval_decision_service = _StaticRetrievalDecisionService(
            RetrievalDecision(
                should_retrieve=False,
                retrieval_type="internet",
                confidence="high",
                reason_code="disabled",
                user_visible_reason="Internet retrieval is disabled, so I cannot check for more current information.",
                explicit_request=False,
                requires_user_confirmation=False,
                search_query="latest news on Iran",
            )
        )

        wire = await orchestrator.handle_request(
            self._request("Is there any more detail on that in the latest news?", req_id="req-news-2")
        )
        response = json.loads(wire)

        self.assertEqual(
            response["payload"]["content"],
            "Internet retrieval is disabled, so I cannot check for more current information.",
        )
        self.assertNotIn("did not explicitly request internet retrieval", response["payload"]["content"].lower())

    async def test_latest_news_prompt_uses_retrieval_and_does_not_fall_back_to_general_knowledge(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["There is no active war in Iran."],
        )
        orchestrator.retrieval_decision_service = _StaticRetrievalDecisionService(
            RetrievalDecision(
                should_retrieve=True,
                retrieval_type="internet",
                confidence="high",
                reason_code="current_news_request",
                user_visible_reason="I’ll check that online.",
                explicit_request=True,
                requires_user_confirmation=False,
                search_query="latest news on the war in Iran",
            )
        )
        retrieval_service = _UnavailableRetrievalService(
            "I could not retrieve online evidence for that request."
        )
        orchestrator.retrieval_service = retrieval_service

        wire = await orchestrator.handle_request(
            self._request("What is the latest news on the war in Iran?", req_id="req-news")
        )
        response = json.loads(wire)

        self.assertEqual(
            response["payload"]["content"],
            "I could not retrieve online evidence for that request.",
        )
        self.assertEqual(orchestrator.llm.prompts, [])
        self.assertEqual(
            orchestrator.retrieval_decision_service.prompts,
            ["What is the latest news on the war in Iran?"],
        )
        self.assertEqual(
            retrieval_service.prompts,
            ["What is the latest news on the war in Iran?"],
        )

    async def test_disabled_latest_news_prompt_returns_transparent_message(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["There is no active war in Iran."],
        )
        orchestrator.retrieval_decision_service = _StaticRetrievalDecisionService(
            RetrievalDecision(
                should_retrieve=False,
                retrieval_type="internet",
                confidence="high",
                reason_code="disabled",
                user_visible_reason="Internet retrieval is disabled right now, so current information cannot be verified.",
                explicit_request=True,
                requires_user_confirmation=False,
                search_query="latest news on the war in Iran",
            )
        )

        wire = await orchestrator.handle_request(
            self._request("What is the latest news on the war in Iran?", req_id="req-news-disabled")
        )
        response = json.loads(wire)

        self.assertEqual(
            response["payload"]["content"],
            "Internet retrieval is disabled right now, so current information cannot be verified.",
        )
        self.assertEqual(orchestrator.llm.prompts, [])
        self.assertEqual(
            orchestrator.retrieval_decision_service.prompts,
            ["What is the latest news on the war in Iran?"],
        )

    async def test_suggest_search_announcement_returns_brief_prompt(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Fallback answer should not be used."],
        )
        orchestrator.retrieval_decision_service = _StaticRetrievalDecisionService(
            RetrievalDecision(
                should_retrieve=False,
                retrieval_type="internet",
                confidence="high",
                reason_code="freshness_release_version",
                user_visible_reason="That may have changed recently. Shall I check online?",
                explicit_request=False,
                requires_user_confirmation=True,
                search_query="current Python release",
            )
        )

        wire = await orchestrator.handle_request(
            self._request("What is the current Python release?", req_id="req-decision")
        )
        response = json.loads(wire)

        self.assertEqual(
            response["payload"]["content"],
            "That may have changed recently. Shall I check online?",
        )
        self.assertEqual(orchestrator.llm.prompts, [])
        self.assertEqual(
            orchestrator.retrieval_decision_service.prompts,
            ["What is the current Python release?"],
        )

    async def test_suggest_search_confirmation_executes_pending_retrieval(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Codex is currently available as described by the retrieved source."],
        )
        orchestrator.retrieval_decision_service = RetrievalDecisionService(
            settings=RetrievalSettings(
                internet_search_enabled=True,
                internet_search_mode="suggest_search",
                default_search_provider="searxng",
                max_search_results=5,
                max_sources_to_fetch=3,
                cache_ttl_hours=1,
                require_citations=True,
            ),
            logger=orac_module.logger,
        )
        pack = GroundingPackBuilder().build(
            SearchRequest(query="current version of Codex", trigger_phrase="freshness_release_version"),
            [SearchResult(title="Codex release", url="https://example.test/codex")],
            [
                FetchedSource(
                    url="https://example.test/codex",
                    title="Codex release",
                    source_name="example.test",
                    text="Codex current release information is available from this source.",
                    excerpt="Codex current release information is available from this source.",
                )
            ],
            require_citations=True,
        )
        retrieval_service = _SuccessfulRetrievalService(pack)
        orchestrator.retrieval_service = retrieval_service

        first_wire = await orchestrator.handle_request(
            self._request("What is the current version of Codex?", req_id="req-codex-confirm")
        )
        first_response = json.loads(first_wire)

        self.assertEqual(
            first_response["payload"]["content"],
            "That may have changed recently. Shall I check online?",
        )
        self.assertIn("clive", orchestrator._pending_retrieval_by_session)

        stream_frames: list[dict[str, object]] = []

        async def _event_sink(event: dict[str, object]) -> None:
            stream_frames.append(dict(event))

        second_wire = await orchestrator.handle_request(
            self._request("Yes", req_id="req-codex-yes", meta={"stream": True}),
            event_sink=_event_sink,
        )
        second_response = json.loads(second_wire)

        self.assertNotIn("clive", orchestrator._pending_retrieval_by_session)
        self.assertEqual(retrieval_service.prompts, ["current version of Codex"])
        frame_types = [str(frame.get("type")) for frame in stream_frames]
        self.assertIn("retrieval_start", frame_types)
        self.assertIn("retrieval_query", frame_types)
        self.assertIn("retrieval_fetch_start", frame_types)
        self.assertIn("retrieval_fetch_complete", frame_types)
        self.assertIn("retrieval_complete", frame_types)
        self.assertIn("Codex is currently available", second_response["payload"]["content"])
        self.assertNotIn("I will check online", second_response["payload"]["content"])
        self.assertNotIn("I'll check that online", second_response["payload"]["content"])
        self.assertNotIn("I’ll check that online", second_response["payload"]["content"])
        self.assertNotIn("grounding pack", second_response["payload"]["content"].lower())

    async def test_suggest_search_rejection_clears_pending_retrieval(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Fallback answer should not be used."],
        )
        orchestrator.retrieval_decision_service = RetrievalDecisionService(
            settings=RetrievalSettings(
                internet_search_enabled=True,
                internet_search_mode="suggest_search",
                default_search_provider="searxng",
                max_search_results=5,
                max_sources_to_fetch=3,
                cache_ttl_hours=1,
                require_citations=True,
            ),
            logger=orac_module.logger,
        )
        retrieval_service = _UnavailableRetrievalService("Retrieval should not run.")
        orchestrator.retrieval_service = retrieval_service

        await orchestrator.handle_request(
            self._request("What is the current version of Codex?", req_id="req-codex-confirm")
        )
        wire = await orchestrator.handle_request(self._request("No", req_id="req-codex-no"))
        response = json.loads(wire)

        self.assertEqual(response["payload"]["content"], "I won't check online.")
        self.assertNotIn("clive", orchestrator._pending_retrieval_by_session)
        self.assertEqual(retrieval_service.prompts, [])

    async def test_suggest_search_new_topic_clears_pending_retrieval(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["The plugin router uses local routing hints."],
        )
        orchestrator.retrieval_decision_service = RetrievalDecisionService(
            settings=RetrievalSettings(
                internet_search_enabled=True,
                internet_search_mode="suggest_search",
                default_search_provider="searxng",
                max_search_results=5,
                max_sources_to_fetch=3,
                cache_ttl_hours=1,
                require_citations=True,
            ),
            logger=orac_module.logger,
        )
        retrieval_service = _UnavailableRetrievalService("Retrieval should not run.")
        orchestrator.retrieval_service = retrieval_service

        await orchestrator.handle_request(
            self._request("What is the current version of Codex?", req_id="req-codex-confirm")
        )
        wire = await orchestrator.handle_request(
            self._request("Actually, how does the Orac plugin router work?", req_id="req-local")
        )
        response = json.loads(wire)

        self.assertIn("plugin router", response["payload"]["content"])
        self.assertNotIn("clive", orchestrator._pending_retrieval_by_session)
        self.assertEqual(retrieval_service.prompts, [])

    async def test_expired_pending_retrieval_is_not_confirmed(self) -> None:
        orchestrator = self._make_orac_stub(llm_responses=["Normal acknowledgement."])
        orchestrator._pending_retrieval_by_session["clive"] = orac_module._PendingRetrievalIntent(
            original_user_message="What is the current version of Codex?",
            topic="current version of Codex",
            search_query="current version of Codex",
            reason_code="freshness_release_version",
            retrieval_type="internet",
            confidence="high",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        retrieval_service = _UnavailableRetrievalService("Retrieval should not run.")
        orchestrator.retrieval_service = retrieval_service

        wire = await orchestrator.handle_request(self._request("Yes", req_id="req-expired-yes"))
        response = json.loads(wire)

        self.assertEqual(response["payload"]["content"], "Normal acknowledgement.")
        self.assertNotIn("clive", orchestrator._pending_retrieval_by_session)
        self.assertEqual(retrieval_service.prompts, [])

    async def test_ambiguous_codecs_query_asks_for_clarification(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Fallback answer should not be used."],
        )
        orchestrator.retrieval_decision_service = RetrievalDecisionService(
            settings=RetrievalSettings(
                internet_search_enabled=True,
                internet_search_mode="suggest_search",
                default_search_provider="searxng",
                max_search_results=5,
                max_sources_to_fetch=3,
                cache_ttl_hours=1,
                require_citations=True,
            ),
            logger=orac_module.logger,
        )
        retrieval_service = _UnavailableRetrievalService("Retrieval should not run.")
        orchestrator.retrieval_service = retrieval_service

        wire = await orchestrator.handle_request(
            self._request("What is the current version of codecs?", req_id="req-codecs")
        )
        response = json.loads(wire)

        self.assertEqual(
            response["payload"]["content"],
            "Do you mean OpenAI Codex, or a specific audio/video codec?",
        )
        self.assertEqual(retrieval_service.prompts, [])
        self.assertNotIn("clive", orchestrator._pending_retrieval_by_session)

    async def test_codecs_query_can_normalise_to_codex_from_recent_retrieval_context(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Codex source-backed answer."],
        )
        orchestrator.retrieval_decision_service = RetrievalDecisionService(
            settings=RetrievalSettings(
                internet_search_enabled=True,
                internet_search_mode="suggest_search",
                default_search_provider="searxng",
                max_search_results=5,
                max_sources_to_fetch=3,
                cache_ttl_hours=1,
                require_citations=True,
            ),
            logger=orac_module.logger,
        )
        orchestrator._retrieval_context_by_session["clive"] = RetrievalTurnContext(
            topic="current version of Codex",
            original_user_message="What is the current version of Codex?",
            retrieval_status="success",
            topic_signature=("codex",),
            explicit_request=True,
        )
        pack = GroundingPackBuilder().build(
            SearchRequest(query="current version of Codex", trigger_phrase="freshness_release_version"),
            [SearchResult(title="Codex release", url="https://example.test/codex")],
            [
                FetchedSource(
                    url="https://example.test/codex",
                    title="Codex release",
                    source_name="example.test",
                    text="Codex release details.",
                    excerpt="Codex release details.",
                )
            ],
            require_citations=True,
        )
        retrieval_service = _SuccessfulRetrievalService(pack)
        orchestrator.retrieval_service = retrieval_service

        await orchestrator.handle_request(
            self._request("What is the current version of codecs?", req_id="req-codecs")
        )
        self.assertEqual(
            orchestrator._pending_retrieval_by_session["clive"].search_query,
            "current version of Codex",
        )
        await orchestrator.handle_request(self._request("yes", req_id="req-codecs-yes"))

        self.assertEqual(retrieval_service.prompts, ["current version of Codex"])

    async def test_disabled_retrieval_returns_clear_failure_without_llm(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Fallback answer should not be used."],
        )
        orchestrator.retrieval_decision_service = _StaticRetrievalDecisionService(
            RetrievalDecision(
                should_retrieve=False,
                retrieval_type="internet",
                confidence="high",
                reason_code="disabled",
                user_visible_reason="Internet retrieval is disabled right now.",
                explicit_request=True,
                requires_user_confirmation=False,
                search_query="latest Python release",
            )
        )

        wire = await orchestrator.handle_request(
            self._request("search the internet for the latest Python release", req_id="req-disabled")
        )
        response = json.loads(wire)

        self.assertEqual(
            response["payload"]["content"],
            "Internet retrieval is disabled right now.",
        )
        self.assertEqual(orchestrator.llm.prompts, [])
        self.assertEqual(
            orchestrator.retrieval_decision_service.prompts,
            ["search the internet for the latest Python release"],
        )

    async def test_persistence_failures_are_recorded_and_logged(self) -> None:
        context_manager = _MemoryContextManager(fail_role="assistant")
        orchestrator = self._make_orac_stub(
            llm_responses=["Normal answer despite persistence failure."],
            context_manager=context_manager,
        )

        wire = await orchestrator.handle_request(self._request("Tell me something.", req_id="req1"))
        response = json.loads(wire)

        self.assertEqual(response["meta"]["status"], "ok")
        self.assertEqual(len(orchestrator._persistence_failures), 1)
        self.assertEqual(orchestrator._persistence_failures[0]["phase"], "assistant_turn")
        errors = "\n".join(message for level, message in orac_module.logger.messages if level == "error")
        self.assertIn("Failed to persist assistant_turn", errors)

    async def test_unregistered_user_sets_anonymous_registration_status(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Hello anonymous user."],
            context_manager=_AnonymousContextManager(),
        )

        wire = await orchestrator.handle_request(self._request("Hello there.", req_id="req1"))
        response = json.loads(wire)

        self.assertEqual(response["meta"]["status"], "ok")
        self.assertEqual(response["meta"]["user_registration"], "anonymous")
        self.assertGreaterEqual(len(orchestrator._persistence_failures), 2)
        errors = "\n".join(message for level, message in orac_module.logger.messages if level == "error")
        self.assertIn("ensure_conversation_with_timeout failed", errors)

    async def test_request_start_reconnects_stale_oracle_session(self) -> None:
        orchestrator = self._make_orac_stub(
            llm_responses=["Hello after reconnect."],
        )
        stale_session = _HealthCheckDBSession(fail_once=True)
        healthy_session = _HealthCheckDBSession(fail_once=False)
        reconnects: list[str] = []
        orchestrator.db_session = stale_session
        orchestrator.ctx.db = stale_session
        orchestrator._user = "svc"
        orchestrator._password = "secret"
        orchestrator._dsn = "db"

        def _fake_refresh() -> None:
            reconnects.append("reconnected")
            orchestrator.db_session = healthy_session
            orchestrator.ctx.db = healthy_session

        orchestrator._refresh_db_session = _fake_refresh  # type: ignore[method-assign]

        wire = await orchestrator.handle_request(self._request("Hello again.", req_id="req-reconnect"))
        response = json.loads(wire)

        self.assertEqual(response["meta"]["status"], "ok")
        self.assertEqual(reconnects, ["reconnected"])
        self.assertIs(orchestrator.db_session, healthy_session)
        self.assertIs(orchestrator.ctx.db, healthy_session)
        self.assertGreaterEqual(healthy_session.health_checks, 1)

    def test_llm_registry_sync_preserves_existing_probe_metadata(self) -> None:
        orchestrator = Orac.__new__(Orac)
        orchestrator.model_name = "qwen2.5:7b"
        orchestrator.llm_service_id = "ollama"
        orchestrator.service_url = "http://localhost:11434"
        orchestrator._available_backend_models = set()
        orchestrator.db_session = _SyncDBSession(
            rows=[
                {
                    "LLM_ID": 42,
                    "NAME": "qwen2.5:7b",
                    "PROVIDER": "ollama",
                    "MODEL": "qwen2.5:7b",
                    "CONTEXT_POLICY": "unresolved",
                    "MAX_CONTEXT_TOKENS": 8192,
                    "IS_ENABLED": "Y",
                    "PROPERTIES": {
                        "size_mb": Decimal("14.2"),
                        "history_probe_status": "complete",
                        "history_probe_total_response_ms": 987,
                        "history_probe_responsiveness_class": "normal",
                    },
                }
            ]
        )
        orchestrator.llm = types.SimpleNamespace(
            list_models=lambda: ["qwen2.5:7b"],
            list_model_details=lambda: [
                {
                    "name": "qwen2.5:7b",
                    "size_bytes": 15461468160,
                    "parameter_size": "7B",
                    "quantization_level": "Q4_K_M",
                }
            ],
        )

        orchestrator._sync_llm_registry()

        self.assertTrue(orchestrator.db_session.committed)
        self.assertEqual(len(orchestrator.db_session.cursor_obj.statements), 1)
        sql, params = orchestrator.db_session.cursor_obj.statements[0]
        self.assertIn("update orac_api.llm_registry_v", sql.lower())
        self.assertEqual(params["context_policy"], "unresolved")
        merged_properties = json.loads(params["properties"])
        self.assertEqual(merged_properties["size_mb"], 14745)
        self.assertEqual(
            merged_properties["history_probe_status"],
            "complete",
        )
        self.assertEqual(
            merged_properties["history_probe_total_response_ms"],
            987,
        )
        self.assertEqual(
            merged_properties["history_probe_responsiveness_class"],
            "normal",
        )
        self.assertEqual(merged_properties["size_bytes"], 15461468160)
        self.assertEqual(merged_properties["size_mb"], 14745)
        self.assertEqual(merged_properties["parameter_size"], "7B")
        self.assertEqual(merged_properties["quantization_level"], "Q4_K_M")
        self.assertEqual(merged_properties["discovered_by"], "startup_sync")
        self.assertEqual(merged_properties["service_url"], "http://localhost:11434")
        self.assertEqual(merged_properties["provider"], "ollama")
        self.assertEqual(merged_properties["model"], "qwen2.5:7b")
        self.assertTrue(merged_properties["is_default_runtime_model"])

    def test_llm_registry_sync_defaults_new_rows_to_unresolved(self) -> None:
        orchestrator = Orac.__new__(Orac)
        orchestrator.model_name = "qwen2.5:7b"
        orchestrator.llm_service_id = "ollama"
        orchestrator.service_url = "http://localhost:11434"
        orchestrator._available_backend_models = set()
        orchestrator.db_session = _SyncDBSession(rows=[])
        orchestrator.llm = types.SimpleNamespace(
            list_models=lambda: ["qwen2.5:7b"],
            list_model_details=lambda: [
                {
                    "name": "qwen2.5:7b",
                    "size_bytes": 15461468160,
                    "parameter_size": "7B",
                    "quantization_level": "Q4_K_M",
                }
            ],
        )

        orchestrator._sync_llm_registry()

        self.assertTrue(orchestrator.db_session.committed)
        self.assertEqual(len(orchestrator.db_session.cursor_obj.statements), 1)
        sql, params = orchestrator.db_session.cursor_obj.statements[0]
        self.assertIn("insert into orac_api.llm_registry_v", sql.lower())
        self.assertEqual(params["context_policy"], "unresolved")
        inserted_properties = json.loads(params["properties"])
        self.assertEqual(inserted_properties["discovered_by"], "startup_sync")
        self.assertEqual(inserted_properties["service_url"], "http://localhost:11434")
        self.assertEqual(inserted_properties["size_bytes"], 15461468160)
        self.assertEqual(inserted_properties["size_mb"], 14745)
        self.assertEqual(inserted_properties["parameter_size"], "7B")
        self.assertEqual(inserted_properties["quantization_level"], "Q4_K_M")

    def test_unresolved_llm_probe_marks_row_complete(self) -> None:
        orchestrator = Orac.__new__(Orac)
        orchestrator.llm_service_id = "ollama"
        orchestrator.service_url = "http://localhost:11434"
        orchestrator.llm = types.SimpleNamespace(
            list_model_details=lambda: [
                {
                    "name": "qwen2.5:7b",
                    "size_bytes": 15461468160,
                    "parameter_size": "7B",
                    "quantization_level": "Q4_K_M",
                }
            ]
        )
        probe_db = _ProbeDBSession(
            rows=[
                {
                    "LLM_ID": 22,
                    "NAME": "qwen2.5:7b",
                    "PROVIDER": "ollama",
                    "MODEL": "qwen2.5:7b",
                    "CONTEXT_POLICY": "unresolved",
                    "PROPERTIES": {
                        "service_url": "http://localhost:11434",
                        "size_mb": Decimal("9.5"),
                    },
                }
            ]
        )
        probe_llm = _ProbeLLM()
        orchestrator._get_llm_connector = lambda **kwargs: probe_llm

        orchestrator._probe_single_llm_registry_row(probe_db, probe_db.rows[0])

        self.assertTrue(probe_db.committed)
        self.assertEqual(len(probe_db.cursor_obj.statements), 1)
        sql, params = probe_db.cursor_obj.statements[0]
        self.assertIn("update orac_api.llm_registry_v", sql.lower())
        self.assertEqual(params["context_policy"], "app")
        merged = json.loads(params["properties"])
        self.assertEqual(merged["history_probe_status"], "complete")
        self.assertEqual(merged["supports_provider_history"], "Y")
        self.assertEqual(merged["history_probe_suggested_context_policy"], "app")
        self.assertEqual(merged["history_probe_responsiveness_class"], "fast")
        self.assertEqual(merged["size_mb"], 14745)
        self.assertEqual(merged["size_bytes"], 15461468160)
        self.assertEqual(merged["parameter_size"], "7B")
        self.assertEqual(merged["quantization_level"], "Q4_K_M")

    def test_non_chat_llm_probe_is_skipped_and_marked_model(self) -> None:
        orchestrator = Orac.__new__(Orac)
        orchestrator.llm_service_id = "ollama"
        orchestrator.service_url = "http://localhost:11434"
        orchestrator.llm = types.SimpleNamespace(
            list_model_details=lambda: [
                {
                    "name": "nomic-embed-text:latest",
                    "size_bytes": 287309056,
                    "parameter_size": "7B",
                    "quantization_level": "Q4_K_M",
                }
            ]
        )
        probe_db = _ProbeDBSession(
            rows=[
                {
                    "LLM_ID": 25,
                    "NAME": "nomic-embed-text:latest",
                    "PROVIDER": "ollama",
                    "MODEL": "nomic-embed-text:latest",
                    "CONTEXT_POLICY": "unresolved",
                    "PROPERTIES": {
                        "service_url": "http://localhost:11434",
                        "size_mb": Decimal("274.0"),
                    },
                }
            ]
        )
        probe_llm = _ProbeLLMShouldNotBeCalled()
        orchestrator._get_llm_connector = lambda **kwargs: probe_llm

        orchestrator._probe_single_llm_registry_row(probe_db, probe_db.rows[0])

        self.assertTrue(probe_db.committed)
        self.assertEqual(probe_llm.calls, 0)
        self.assertEqual(len(probe_db.cursor_obj.statements), 1)
        sql, params = probe_db.cursor_obj.statements[0]
        self.assertIn("update orac_api.llm_registry_v", sql.lower())
        self.assertEqual(params["context_policy"], "model")
        merged = json.loads(params["properties"])
        self.assertEqual(merged["history_probe_status"], "skipped_non_chat_model")
        self.assertEqual(merged["supports_provider_history"], "N")
        self.assertEqual(merged["history_probe_suggested_context_policy"], "model")
        self.assertEqual(merged["history_probe_responsiveness_class"], "skipped")
        self.assertIsNone(merged["history_probe_first_response_ms"])
        self.assertIsNone(merged["history_probe_second_response_ms"])
        self.assertIsNone(merged["history_probe_total_response_ms"])
        self.assertEqual(merged["size_bytes"], 287309056)
        self.assertEqual(merged["size_mb"], 274)
        self.assertEqual(merged["parameter_size"], "7B")
        self.assertEqual(merged["quantization_level"], "Q4_K_M")

    def test_failed_llm_probe_is_marked_model_to_avoid_retry_loop(self) -> None:
        orchestrator = Orac.__new__(Orac)
        orchestrator.llm_service_id = "ollama"
        orchestrator.service_url = "http://localhost:11434"
        orchestrator.llm = types.SimpleNamespace(
            list_model_details=lambda: [
                {
                    "name": "deepseek-r1-14b-64k:latest",
                    "size_bytes": 999,
                    "parameter_size": "14B",
                    "quantization_level": "Q4_K_M",
                }
            ]
        )
        probe_db = _ProbeDBSession(
            rows=[
                {
                    "LLM_ID": 24,
                    "NAME": "deepseek-r1-14b-64k:latest",
                    "PROVIDER": "ollama",
                    "MODEL": "deepseek-r1-14b-64k:latest",
                    "CONTEXT_POLICY": "unresolved",
                    "PROPERTIES": {
                        "service_url": "http://localhost:11434",
                    },
                }
            ]
        )
        orchestrator._get_llm_connector = lambda **kwargs: _ProbeLLMBackendFailure()

        orchestrator._probe_single_llm_registry_row(probe_db, probe_db.rows[0])

        self.assertTrue(probe_db.committed)
        self.assertEqual(len(probe_db.cursor_obj.statements), 1)
        sql, params = probe_db.cursor_obj.statements[0]
        self.assertIn("update orac_api.llm_registry_v", sql.lower())
        self.assertEqual(params["context_policy"], "model")
        merged = json.loads(params["properties"])
        self.assertEqual(merged["history_probe_status"], "failed")
        self.assertEqual(merged["supports_provider_history"], "N")
        self.assertEqual(merged["history_probe_suggested_context_policy"], "model")
        self.assertEqual(merged["history_probe_responsiveness_class"], "failed")
        self.assertIn("404 Client Error", merged["history_probe_error"])
        self.assertEqual(merged["size_bytes"], 999)
        self.assertEqual(merged["parameter_size"], "14B")


class OracContextManagerLoadTests(unittest.TestCase):
    """Tests low-level context loading semantics."""

    def test_load_context_limit_returns_newest_rows_in_chronological_order(self) -> None:
        manager = OracContextManager(db=_FakeDBSession(), logger=_FakeLogger())
        manager._conversation_id = lambda session_id: 1  # type: ignore[method-assign]

        rows = manager.load_context(session_id="clive", limit=2)

        self.assertEqual([row["TURN_INDEX"] for row in rows], [4, 5])
        self.assertEqual([row["CONTENT"]["text"] for row in rows], ["four", "five"])

    def test_timeout_reuses_recent_open_conversation(self) -> None:
        recent_ts = datetime.now(timezone.utc) - timedelta(seconds=30)
        manager = OracContextManager(db=_TimeoutDBSession(recent_ts), logger=_FakeLogger())

        result = manager.ensure_conversation_with_timeout(
            user_name="clive",
            session_id_base="clive",
            llm_id=None,
            timeout_seconds=3600,
        )

        self.assertFalse(result["rolled_over"])
        self.assertEqual(result["conversation_id"], 99)
        self.assertEqual(result["session_id"], "clive#existing")
        self.assertLess(result["age_seconds"], 3600)


if __name__ == "__main__":
    unittest.main()
