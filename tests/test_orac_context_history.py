"""Tests for Orac context continuity and persistence visibility.

# Author: Clive Bostock
# Date: 2026-04-26
# Description: Verifies current Orac context continuity across normal and
#   plugin-handled turns without redesigning the runtime flow.
"""

from __future__ import annotations

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
from model.plugin_runtime import PluginExecutionResult


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

    def send_prompt(self, prompt_type: str, prompt: str, stream: bool = False) -> str:
        del prompt_type, stream
        self.prompts.append(prompt)
        if self._responses:
            return self._responses.pop(0)
        return "stubbed response"

    def send_prompt_with_meta(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
    ) -> dict[str, int | str]:
        text = self.send_prompt(prompt_type=prompt_type, prompt=prompt, stream=stream)
        return {
            "text": text,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }


class _ProbeLLM:
    """Returns probe responses based on the prompt content."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def send_prompt_with_meta(
        self,
        prompt_type: str,
        prompt: str,
        stream: bool = False,
    ) -> dict[str, int | str]:
        del prompt_type, stream
        self.prompts.append(prompt)
        if "and nothing else" in prompt and "Recent exchange" not in prompt:
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


class _MemoryContextManager:
    """Small in-memory stand-in for Orac context persistence."""

    def __init__(self, fail_role: str | None = None) -> None:
        self.fail_role = fail_role
        self.messages_by_session: dict[str, list[dict[str, str]]] = {}
        self.conversation_ids: dict[str, int] = {}
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
        del llm_id, timeout_seconds
        if session_id_base not in self.conversation_ids:
            self.conversation_ids[session_id_base] = self._next_conversation_id
            self._next_conversation_id += 1
            self.messages_by_session.setdefault(session_id_base, [])
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
        del user_name, llm_id
        if session_id not in self.conversation_ids:
            self.conversation_ids[session_id] = self._next_conversation_id
            self._next_conversation_id += 1
            self.messages_by_session.setdefault(session_id, [])
        return self.conversation_ids[session_id]

    def _save(self, session_id: str, role: str, text: str) -> dict[str, int]:
        if self.fail_role == role:
            raise RuntimeError(f"Simulated {role} persistence failure")
        bucket = self.messages_by_session.setdefault(session_id, [])
        turn_index = len(bucket) + 1
        bucket.append({"role": role, "content": text})
        self.saved_events.append((session_id, role, text))
        return {
            "conversation_id": self.conversation_ids.setdefault(session_id, self._next_conversation_id),
            "message_id": turn_index,
            "turn_index": turn_index,
        }

    def last_turn_index(self, session_id: str) -> int:
        return len(self.messages_by_session.get(session_id, []))

    def save_system_turn(self, session_id: str, user_name: str, text: str, *, meta=None, llm_id=None) -> dict[str, int]:
        del user_name, meta, llm_id
        return self._save(session_id, "system", text)

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
        del user_name, meta, llm_id, tokens_used
        return self._save(session_id, "user", text)

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
        del user_name, meta, llm_id, tokens_used
        return self._save(session_id, "assistant", text)

    def get_messages_for_prompt(self, session_id: str, limit: int = 20) -> list[dict[str, str]]:
        del limit
        return list(self.messages_by_session.get(session_id, []))

    def get_user_profile(self, username: str) -> dict[str, str]:
        return {
            "authenticated_username": username,
            "display_name": "Clive",
        }

    def get_user_preference_value(self, *args, **kwargs) -> str | None:
        del args, kwargs
        return None

    def get_orac_personality(self, personality_code: str) -> dict[str, str] | None:
        del personality_code
        return None

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
        return {
            "LLM_ID": llm_id,
            "PROVIDER": "ollama",
            "MODEL": "test-model",
            "IS_ENABLED": "Y",
        }

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

    def get_conversation_llm_id(self, session_id: str) -> int:
        del session_id
        return 1

    def set_conversation_title(self, session_id: str, title: str) -> None:
        self.titles[session_id] = title

    def archive_conversation(self, session_id: str) -> None:
        del session_id

    def close_conversation(self, session_id: str) -> None:
        del session_id


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
    ) -> PluginExecutionResult | None:
        del meta, handoff, auth_user
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
        orchestrator.config_mgr = object()
        orchestrator._system_prompt_policy = {
            "title": "SYSTEM POLICY — ORAC PERSONA:",
            "identity": {
                "assistant_name": "Orac",
                "disallowed_vendor_claims": ["DeepSeek", "OpenAI"],
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
                    "You MUST use information the user has voluntarily shared in this conversation to answer their questions.",
                    "When asked about personal details (name, location, preferences, etc.), check the conversation history first.",
                    "If the user previously mentioned a fact in this conversation, reference it directly.",
                    "For ordinary factual questions, use your general knowledge as well as relevant context from the recent exchange.",
                    "Do not treat earlier assistant answers as authoritative if they conflict with reliable knowledge; correct materially wrong earlier answers plainly.",
                    "For personal or session-specific facts, only say you know them when they are present in authenticated context or the recent exchange.",
                    "When a user likely misspells or uses a variant of a well-known proper noun, state the likely interpretation and answer under that interpretation; ask for clarification only if multiple plausible meanings remain.",
                    "Treat elliptical follow-up prompts such as 'tell me more', 'go on', 'explain that', 'why?', and similar short continuations as referring to the immediately preceding assistant answer unless the user clearly changes topic.",
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
    def _request(prompt: str, *, req_id: str) -> str:
        return json.dumps(
            {
                "v": 1,
                "type": "request",
                "id": req_id,
                "ts": "2026-04-26T10:00:00Z",
                "route": "orac.prompt",
                "meta": {"client": "apex"},
                "payload": {"messages": [{"role": "user", "content": prompt}]},
            },
            ensure_ascii=False,
        )

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
        self.assertIn("USER (new message):\nTell me more", follow_up_prompt)

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
            "USER (new message):\nHow did king Henry manage to win?",
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
        self.assertIn("USER (new message):\nTis a miracle.", reaction_prompt)

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
                        "size_mb": 14.2,
                        "history_probe_status": "complete",
                        "history_probe_total_response_ms": 987,
                        "history_probe_responsiveness_class": "normal",
                    },
                }
            ]
        )
        orchestrator.llm = types.SimpleNamespace(
            list_models=lambda: ["qwen2.5:7b"]
        )

        orchestrator._sync_llm_registry()

        self.assertTrue(orchestrator.db_session.committed)
        self.assertEqual(len(orchestrator.db_session.cursor_obj.statements), 1)
        sql, params = orchestrator.db_session.cursor_obj.statements[0]
        self.assertIn("update orac_api.llm_registry_v", sql.lower())
        self.assertEqual(params["context_policy"], "unresolved")
        merged_properties = json.loads(params["properties"])
        self.assertEqual(merged_properties["size_mb"], 14.2)
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
            list_models=lambda: ["qwen2.5:7b"]
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

    def test_unresolved_llm_probe_marks_row_complete(self) -> None:
        orchestrator = Orac.__new__(Orac)
        orchestrator.llm_service_id = "ollama"
        orchestrator.service_url = "http://localhost:11434"
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
                        "size_mb": 9.5,
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
        self.assertEqual(merged["size_mb"], 9.5)


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
