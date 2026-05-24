"""Conversation persistence helpers for Orac's Oracle-backed context store."""

# Author: Clive Bostock
# Date: 2026-04-25
# Description: Persist and retrieve conversation context through the published
#   Orac database object surface.

from __future__ import annotations
from typing import Optional, List, Dict, Any
import json
import os
import time
from datetime import datetime, timezone
import oracledb  # for error code inspection
from lib.session_manager import DBSession  # <- your DBSession wrapper


class OracContextManager:
    """
    Minimal Oracle-backed context manager for Orac:
      - Resolves user by username (auto-provision optional; OFF by default)
      - Resolves/creates conversation by session_id (unique)
      - Appends messages with safe turn_index (retries on ORA-00001)
      - Loads/prunes/deletes conversation context
    """

    def __init__(self, db: DBSession, *, allow_auto_provision_users: bool = False, logger):
        self.db = db
        self.allow_auto = bool(allow_auto_provision_users)
        self.logger = logger
        self.object_schema = os.getenv("ORAC_DB_OBJECT_SCHEMA", "orac_apx_pub").strip().lower()
        self.users_object = self._qualify("users")
        self.conversations_object = self._qualify("conversations_v")
        self.messages_object = self._qualify("messages_v")
        self.user_preferences_object = self._qualify("user_preferences_v")
        self.orac_personalities_object = "orac_api.orac_personalities_v"
        self.model_generation_presets_object = "orac_api.model_generation_presets_v"
        self.llm_registry_object = "orac_api.llm_registry_v"

    def _qualify(self, object_name: str) -> str:
        """Return a schema-qualified object name for runtime SQL."""
        if self.object_schema:
            return f"{self.object_schema}.{object_name}"
        return object_name

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------


    def _conversation_id(self, session_id: str) -> Optional[int]:
        rows = self.db.dict_sql_dataset(
            f"select conversation_id from {self.conversations_object} where session_id = :s",
            {"s": session_id}
        )
        return int(rows[0]["CONVERSATION_ID"]) if rows else None

    def _next_turn_index(self, conversation_id: int) -> int:
        rows = self.db.fetch_as_lists(
            f"select nvl(max(turn_index),0)+1 from {self.messages_object} where conversation_id = :cid",
            {"cid": conversation_id}
        )
        return int(rows[0][0]) if rows else 1

    def _set_conversation_llm_id_if_null(
        self,
        conversation_id: int,
        llm_id: Optional[int],
    ) -> None:
        """Persist an LLM id for a conversation only when the row is currently null."""
        if not conversation_id or llm_id is None:
            return

        with self.db.cursor() as cur:
            cur.execute(
                f"""
                update {self.conversations_object}
                   set llm_id = :llm_id
                 where conversation_id = :conversation_id
                   and llm_id is null
                """,
                {
                    "llm_id": llm_id,
                    "conversation_id": conversation_id,
                },
            )
            self.db.commit()

    # --- user helpers ---------------------------------------------------------

    def _find_user_id(self, username: str) -> Optional[int]:
        norm = (username or "").strip()
        if not norm:
            return None
        rows = self.db.dict_sql_dataset(
            f"select user_id from {self.users_object} where username = :u",
            {"u": norm}
        )
        return int(rows[0]["USER_ID"]) if rows else None

    def get_user_profile(self, username: str) -> Dict[str, str]:
        """Return stable profile facts for an authenticated runtime user."""
        norm = (username or "").strip()
        if not norm:
            return {}

        rows = self.db.dict_sql_dataset(
            (
                f"select username, display_name "
                f"from {self.users_object} "
                f"where username = :u"
            ),
            {"u": norm},
        )
        if not rows:
            return {}

        row = rows[0]
        profile: Dict[str, str] = {
            "authenticated_username": row.get("USERNAME") or norm,
        }
        display_name = row.get("DISPLAY_NAME")
        if display_name:
            profile["display_name"] = display_name
        return profile

    def get_user_preference_value(self, username: str, pref_key: str) -> Any | None:
        """Return a deserialised user preference value when one exists."""
        norm = (username or "").strip()
        pref = (pref_key or "").strip()
        if not norm or not pref:
            return None

        rows = self.db.dict_sql_dataset(
            (
                f"select json_serialize(pref_value returning clob null on error) as pref_value "
                f"from {self.user_preferences_object} "
                f"where user_id = ("
                f"  select user_id "
                f"    from {self.users_object} "
                f"   where username = :u"
                f") "
                f"and pref_key = :k"
            ),
            {"u": norm, "k": pref},
        )
        if not rows:
            return None

        raw_value = rows[0].get("PREF_VALUE")
        if raw_value is None:
            return None

        if hasattr(raw_value, "read"):
            try:
                raw_value = raw_value.read()
            except Exception:
                pass

        try:
            return json.loads(raw_value)
        except Exception:
            return raw_value

    def get_orac_personality(self, personality_code: str) -> Dict[str, Any]:
        """Return an active Orac personality definition by code."""
        code = (personality_code or "").strip().upper()
        if not code:
            return {}

        rows = self.db.dict_sql_dataset(
            (
                f"select personality_code,"
                f"       personality_name,"
                f"       description,"
                f"       attitude_base_level,"
                f"       sarcasm_level,"
                f"       verbosity_level,"
                f"       allow_humour,"
                f"       allow_critique,"
                f"       enforce_precision,"
                f"       admit_uncertainty,"
                f"       packaged_persona,"
                f"       model_preset_id,"
                f"       system_prompt,"
                f"       style_prompt,"
                f"       is_active "
                f"from {self.orac_personalities_object} "
                f"where upper(personality_code) = :code "
                f"  and is_active = true"
            ),
            {"code": code},
        )
        return rows[0] if rows else {}

    def get_model_generation_preset(
        self,
        *,
        model_preset_id: int | str | None = None,
        model_preset_code: str | None = None,
    ) -> Dict[str, Any]:
        """Return an active model generation preset by id or code."""
        params: Dict[str, Any]
        predicate: str

        if model_preset_id not in (None, ""):
            try:
                resolved_id = int(model_preset_id)
            except Exception:
                return {}
            predicate = "model_preset_id = :preset_id"
            params = {"preset_id": resolved_id}
        else:
            code = (model_preset_code or "").strip().upper()
            if not code:
                return {}
            predicate = "upper(model_preset_code) = :preset_code"
            params = {"preset_code": code}

        rows = self.db.dict_sql_dataset(
            (
                f"select model_preset_id,"
                f"       model_preset_code,"
                f"       model_preset_name,"
                f"       description,"
                f"       temperature,"
                f"       top_p,"
                f"       top_k,"
                f"       repeat_penalty,"
                f"       num_predict,"
                f"       seed,"
                f"       is_system_preset,"
                f"       is_active "
                f"from {self.model_generation_presets_object} "
                f"where {predicate} "
                f"  and is_active = 'Y'"
            ),
            params,
        )
        return rows[0] if rows else {}

    def get_llm_registry_entry(self, llm_id: int | str | None) -> Dict[str, Any]:
        """Return an LLM registry row by primary key."""
        if llm_id in (None, ""):
            return {}

        try:
            resolved_llm_id = int(llm_id)
        except Exception:
            return {}

        rows = self.db.dict_sql_dataset(
            (
                f"select llm_id,"
                f"       name,"
                f"       provider,"
                f"       model,"
                f"       context_policy,"
                f"       max_context_tokens,"
                f"       is_enabled,"
                f"       properties "
                f"from {self.llm_registry_object} "
                f"where llm_id = :llm_id"
            ),
            {"llm_id": resolved_llm_id},
        )
        return rows[0] if rows else {}

    def get_llm_registry_entry_by_provider_model(
        self,
        provider: str,
        model_name: str,
    ) -> Dict[str, Any]:
        """Return an LLM registry row for a provider/model pair."""
        provider_norm = (provider or "").strip().lower()
        model_norm = (model_name or "").strip()
        if not provider_norm or not model_norm:
            return {}

        rows = self.db.dict_sql_dataset(
            (
                f"select llm_id,"
                f"       name,"
                f"       provider,"
                f"       model,"
                f"       context_policy,"
                f"       max_context_tokens,"
                f"       is_enabled,"
                f"       properties "
                f"from {self.llm_registry_object} "
                f"where lower(provider) = :provider "
                f"  and model = :model "
                f"fetch first 1 row only"
            ),
            {"provider": provider_norm, "model": model_norm},
        )
        return rows[0] if rows else {}

    def get_conversation_llm_id(self, session_id: str) -> Optional[int]:
        """Return the stored LLM id for a conversation session."""
        rows = self.db.dict_sql_dataset(
            (
                f"select llm_id "
                f"from {self.conversations_object} "
                f"where session_id = :session_id"
            ),
            {"session_id": session_id},
        )
        if not rows:
            return None

        value = rows[0].get("LLM_ID")
        if value is None:
            return None

        try:
            return int(value)
        except Exception:
            return None

    def get_conversation_personality_code(self, session_id: str) -> Optional[str]:
        """Return the stored personality code from the conversation primer meta."""
        cid = self._conversation_id(session_id)
        if not cid:
            return None

        rows = self.db.dict_sql_dataset(
            (
                f"select json_value(meta, '$.personality_code' returning varchar2(30) null on error) "
                f"         as personality_code "
                f"from {self.messages_object} "
                f"where conversation_id = :cid "
                f"  and role = 'system' "
                f"  and turn_index = 1"
            ),
            {"cid": cid},
        )
        if not rows:
            return None

        value = rows[0].get("PERSONALITY_CODE")
        if value is None:
            return None

        resolved = str(value).strip().upper()
        return resolved or None

    def get_conversation_prompt_policy_fingerprint(
        self,
        session_id: str,
    ) -> Optional[str]:
        """Return the stored prompt policy fingerprint for a conversation."""
        cid = self._conversation_id(session_id)
        if not cid:
            return None

        rows = self.db.dict_sql_dataset(
            (
                "select json_value("
                "meta, '$.prompt_policy_fingerprint' "
                "returning varchar2(128) null on error"
                ") as prompt_policy_fingerprint "
                f"from {self.messages_object} "
                "where conversation_id = :cid "
                "  and role = 'system' "
                "  and turn_index = 1"
            ),
            {"cid": cid},
        )
        if not rows:
            return None

        value = rows[0].get("PROMPT_POLICY_FINGERPRINT")
        if value is None:
            return None

        resolved = str(value).strip()
        return resolved or None

    def _create_user(self, username: str) -> int:
        norm = username.strip()
        with self.db.cursor() as cur:
            out_id = cur.var(oracledb.NUMBER)
            cur.execute(
                f"insert into {self.users_object}(username, is_active) "
                "values(:1, 'y') returning user_id into :2",
                [norm, out_id]
            )
            self.db.commit()
            val = out_id.getvalue()
            return int(val[0]) if isinstance(val, list) else int(val)

    def _require_user(self, username: str) -> int:
        """
        Lookup only; optionally auto-create based on policy.
        Raises PermissionError if not found and auto-provision is disabled.
        """
        norm = username.strip()  # ensure consistent lookup/logging
        uid = self._find_user_id(norm)
        if uid is not None:
            return uid

        if self.allow_auto:
            return self._create_user(norm)

        # No user found and auto-provision disabled
        self.logger.log_warning(
            f"❌ Invalid user login attempt: '{norm}' not found in {self.users_object}"
        )
        raise PermissionError(f"user '{norm}' is not registered")

    def _get_or_create_conversation(self, user_id: int, session_id: str, llm_id: Optional[int]) -> int:
        rows = self.db.dict_sql_dataset(
            (
                f"select conversation_id, llm_id "
                f"from {self.conversations_object} "
                f"where user_id = :u and session_id = :s"
            ),
            {"u": user_id, "s": session_id}
        )
        if rows:
            conversation_id = int(rows[0]["CONVERSATION_ID"])
            if rows[0].get("LLM_ID") is None and llm_id is not None:
                self._set_conversation_llm_id_if_null(conversation_id, llm_id)
            return conversation_id

        with self.db.cursor() as cur:
            out_id = cur.var(oracledb.NUMBER)
            cur.execute(
                f"insert into {self.conversations_object}(user_id, session_id, llm_id, state) "
                "values(:1, :2, :3, 'open') returning conversation_id into :4",
                [user_id, session_id, llm_id, out_id]
            )
            self.db.commit()
            val = out_id.getvalue()
            return int(val[0]) if isinstance(val, list) else int(val)

    # --- replace the whole helper with this ---
    def _last_activity_epoch(self, conversation_id: int) -> float:
        """
        Returns last-activity time as UNIX epoch seconds (UTC) for a conversation,
        computed in SQL to avoid Python tz/naive datetime pitfalls.
        Falls back to 'now' if there are no messages yet.
        """
        rows = self.db.fetch_as_lists(
            f"""
            select
              (cast(sys_extract_utc(max(created_on)) as date) - date '1970-01-01') * 86400
            from {self.messages_object}
            where conversation_id = :cid
            """,
            {"cid": conversation_id}
        )
        if rows and rows[0][0] is not None:
            try:
                return float(rows[0][0])
            except Exception:
                pass
        return time.time()

    def ensure_conversation_with_timeout(
            self, *,
            user_name: str,
            session_id_base: str,  # only used when creating a NEW conversation row
            llm_id: Optional[int],
            timeout_seconds: int
    ) -> Dict[str, Any]:
        user_id = self._require_user(user_name)

        rows = self.db.dict_sql_dataset(
            f"""
            select conv_id,
                   session_id,
                   llm_id,
                   last_ts
            from (
              select
                c.conversation_id as conv_id,
                c.session_id      as session_id,
                c.llm_id          as llm_id,
                coalesce(
                  max(m.created_on),
                  c.updated_on,
                  c.created_on
                ) as last_ts
              from {self.conversations_object} c
              left join {self.messages_object} m
                on m.conversation_id = c.conversation_id
              where c.user_id = :user_id
                and c.state   = 'open'
              group by c.conversation_id, c.session_id, c.llm_id, c.created_on, c.updated_on
            )
            order by last_ts desc
            fetch first 1 row only
            """,
            {"user_id": user_id}
        )

        if rows:
            conv_id = int(rows[0]["CONV_ID"])
            sid = rows[0]["SESSION_ID"]
            age_sec = self._age_seconds(rows[0].get("LAST_TS"))

            if timeout_seconds <= 0 or age_sec < float(timeout_seconds):
                if rows[0].get("LLM_ID") is None and llm_id is not None:
                    self._set_conversation_llm_id_if_null(conv_id, llm_id)
                return {
                    "conversation_id": conv_id,
                    "session_id": sid,
                    "rolled_over": False,
                    "age_seconds": age_sec,
                    "previous_conversation_id": conv_id,
                    "previous_session_id": sid,
                }

        # Stale or none found -> create a brand-new session_id that cannot collide
        # Use a simple epoch suffix; you could use a monotonic counter if you prefer.
        suffix = str(int(time.time()))
        new_sid = f"{session_id_base}#{suffix}"
        new_cid = self.ensure_conversation(user_name=user_name, session_id=new_sid, llm_id=llm_id)

        return {
            "conversation_id": new_cid,
            "session_id": new_sid,
            "rolled_over": True,
            "age_seconds": float("inf") if rows else 0.0,
            # let caller optionally transition the previous one:
            "previous_conversation_id": int(rows[0]["CONV_ID"]) if rows else None,
            "previous_session_id": rows[0]["SESSION_ID"] if rows else None,
        }

    def _age_seconds(self, last_ts: Any) -> float:
        """Return age in seconds for an Oracle timestamp-like value."""
        if last_ts is None:
            return float("inf")

        if isinstance(last_ts, datetime):
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            else:
                last_ts = last_ts.astimezone(timezone.utc)
            return max(0.0, (datetime.now(timezone.utc) - last_ts).total_seconds())

        for parse_fmt in (
            "%d-%b-%y %I.%M.%S.%f %p",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                parsed = datetime.strptime(str(last_ts), parse_fmt).replace(
                    tzinfo=timezone.utc
                )
                return max(
                    0.0, (datetime.now(timezone.utc) - parsed).total_seconds()
                )
            except ValueError:
                continue

        return float("inf")

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def ensure_conversation(self, *, user_name: str, session_id: str,
                            llm_id: Optional[int] = None) -> int:
        """Ensures user exists and conversation exists; returns conversation_id."""
        user_id = self._require_user(user_name)
        return self._get_or_create_conversation(user_id, session_id, llm_id)

    def save_context(self, session_id: str, role: str, content_obj: dict, *,
                     user_name: str,
                     llm_id: Optional[int] = None,
                     meta: Optional[dict] = None,
                     tokens_used: Optional[int] = None) -> Dict[str, int]:
        """
        Persists a single message and returns identifiers.
        Concurrency: retries on ORA-00001 (unique turn per conversation).
        """
        assert role in ("system", "user", "assistant", "tool")
        content_json = json.dumps(content_obj, ensure_ascii=False)
        meta_json = json.dumps(meta or {}, ensure_ascii=False)

        user_id = self._require_user(user_name)
        conv_id = self._get_or_create_conversation(user_id, session_id, llm_id)

        # light retry loop for (conversation_id, turn_index) unique races
        for _ in range(5):
            turn_index = self._next_turn_index(conv_id)
            try:
                with self.db.cursor() as cur:
                    out_id = cur.var(oracledb.NUMBER)
                    cur.execute(
                        f"insert into {self.messages_object}("
                        "  conversation_id, turn_index, role, content, tokens_used, meta, llm_id"
                        ") values ("
                        "  :1, :2, :3, :4, :5, :6, :7"
                        ") returning message_id into :8",
                        [conv_id, turn_index, role, content_json, tokens_used, meta_json, llm_id, out_id]
                    )
                    # NEW: bump last-activity marker on the conversation
                    cur.execute(
                        f"update {self.conversations_object} set updated_on = systimestamp where conversation_id = :cid",
                        {"cid": conv_id}
                    )
                    self.db.commit()
                    val = out_id.getvalue()
                    msg_id = int(val[0]) if isinstance(val, list) else int(val)
                return {"conversation_id": conv_id, "message_id": msg_id, "turn_index": turn_index}
            except oracledb.DatabaseError as e:
                # ORA-00001 unique constraint (on conv_id, turn_index) – retry
                if hasattr(e, "args") and e.args and "ORA-00001" in str(e):
                    time.sleep(0.02)
                    continue
                raise

        raise RuntimeError("Failed to insert message after retries (turn_index contention).")

    # --- Convenience writers (thin shims over save_context) ----------------------

    def save_user_turn(self, session_id: str, user_name: str, text: str, *,
                       meta: Optional[dict] = None, llm_id: Optional[int] = None,
                       tokens_used: Optional[int] = None) -> Dict[str, int]:
        return self.save_context(
            session_id=session_id, role="user", content_obj={"text": text},
            user_name=user_name, llm_id=llm_id, meta=meta, tokens_used=tokens_used
        )

    def save_assistant_turn(self, session_id: str, user_name: str, text: str, *,
                            meta: Optional[dict] = None, llm_id: Optional[int] = None,
                            tokens_used: Optional[int] = None) -> Dict[str, int]:
        return self.save_context(
            session_id=session_id, role="assistant", content_obj={"text": text},
            user_name=user_name, llm_id=llm_id, meta=meta, tokens_used=tokens_used
        )

    def save_system_turn(self, session_id: str, user_name: str, text: str, *,
                         meta: Optional[dict] = None, llm_id: Optional[int] = None) -> Dict[str, int]:
        return self.save_context(
            session_id=session_id, role="system", content_obj={"text": text},
            user_name=user_name, llm_id=llm_id, meta=meta, tokens_used=None
        )

    # --- Tiny readers useful to orchestration/policy -----------------------------

    def last_turn_index(self, session_id: str) -> int:
        """Return the current max turn_index for this conversation (0 if none)."""
        cid = self._conversation_id(session_id)
        if not cid:
            return 0
        rows = self.db.fetch_as_lists(
            f"select nvl(max(turn_index),0) from {self.messages_object} where conversation_id = :cid",
            {"cid": cid}
        )
        return int(rows[0][0]) if rows else 0

    def load_context(self, session_id: str, limit: Optional[int] = None,
                     include_system: bool = True) -> List[Dict[str, Any]]:
        """
        Returns a list of messages in ascending turn order.
        Each row: {TURN_INDEX, ROLE, CONTENT(JSON), TOKENS_USED, META(JSON), CREATED_ON}
        """
        cid = self._conversation_id(session_id)
        if not cid:
            return []

        role_filter = "" if include_system else "and role <> 'system'"

        if limit and limit > 0:
            sql = f"""
                select turn_index, role, content, tokens_used, meta, created_on
                  from (
                    select turn_index, role, content, tokens_used, meta, created_on
                      from {self.messages_object}
                     where conversation_id = :cid
                       {role_filter}
                     order by turn_index desc
                     fetch first {int(limit)} rows only
                  )
                 order by turn_index
            """
        else:
            sql = f"""
                select turn_index, role, content, tokens_used, meta, created_on
                  from {self.messages_object}
                 where conversation_id = :cid
                   {role_filter}
                 order by turn_index
            """
        rows = self.db.dict_sql_dataset(sql, {"cid": cid})
        # Ensure JSON comes back as Python objects
        for r in rows:
            # Depending on driver, JSON may already be dicts; be defensive:
            if isinstance(r.get("CONTENT"), str):
                try:
                    r["CONTENT"] = json.loads(r["CONTENT"])
                except Exception:
                    pass
            if isinstance(r.get("META"), str):
                try:
                    r["META"] = json.loads(r["META"])
                except Exception:
                    pass
        return rows

    def get_messages_for_prompt(self, session_id: str, limit: int = 20) -> List[Dict[str, str]]:
        """
        Returns OpenAI-like messages list for a prompt:
        [{'role': 'user'|'assistant'|'system'|'tool', 'content': '...'}, ...]
        Uses 'text' field of CONTENT if present, else dumps JSON compactly.
        """
        rows = self.load_context(session_id=session_id, limit=limit, include_system=True)
        out: List[Dict[str, str]] = []
        for r in rows:
            content = r.get("CONTENT")
            if isinstance(content, dict) and "text" in content and isinstance(content["text"], str):
                text = content["text"]
            else:
                # fallback: compact JSON
                try:
                    text = json.dumps(content, ensure_ascii=False, separators=(",", ":"))
                except Exception:
                    text = str(content)
            out.append({"role": r["ROLE"], "content": text})
        return out

    def prune_context(self, session_id: str, *, keep_messages: int = 100,
                      archive_conversation: bool = False) -> int:
        """
        Keeps only the last `keep_messages` by turn_index.
        Returns: number of deleted rows.
        If archive_conversation=True and nothing left to delete, marks conv state 'archived'.
        """
        cid = self._conversation_id(session_id)
        if not cid:
            return 0

        # find threshold turn_index
        rows = self.db.fetch_as_lists(
            f"select max(turn_index) from {self.messages_object} where conversation_id = :cid",
            {"cid": cid}
        )
        max_ti = int(rows[0][0]) if rows and rows[0][0] is not None else 0
        if max_ti <= keep_messages:
            if archive_conversation:
                self.archive_conversation(session_id)
            return 0

        cutoff = max_ti - keep_messages
        with self.db.cursor() as cur:
            cur.execute(
                f"delete from {self.messages_object} "
                " where conversation_id = :cid and turn_index <= :cutoff",
                {"cid": cid, "cutoff": cutoff}
            )
            deleted = cur.rowcount or 0
            self.db.commit()

        if archive_conversation:
            self.archive_conversation(session_id)

        return int(deleted)

    def delete_context(self, session_id: str, *, hard: bool = False) -> None:
        """
        Deletes all messages for the session. If hard=True, also deletes the conversation row.
        Otherwise, sets conversation.state='archived'.
        """
        cid = self._conversation_id(session_id)
        if not cid:
            return

        with self.db.cursor() as cur:
            cur.execute(f"delete from {self.messages_object} where conversation_id = :cid", {"cid": cid})
            if hard:
                cur.execute(f"delete from {self.conversations_object} where conversation_id = :cid", {"cid": cid})
            else:
                cur.execute(
                    f"update {self.conversations_object} set state = 'archived' where conversation_id = :cid",
                    {"cid": cid}
                )
        self.db.commit()

    def set_conversation_title(self, session_id: str, title: str) -> None:
        """Sets/updates the conversation title."""
        cid = self._conversation_id(session_id)
        if not cid:
            return
        self.db.execute(
            f"update {self.conversations_object} set title = :t where conversation_id = :cid",
            {"t": title[:200], "cid": cid}
        )

    def close_conversation(self, session_id: str) -> None:
        """Marks a conversation as 'closed'."""
        cid = self._conversation_id(session_id)
        if not cid:
            return
        self.db.execute(
            f"update {self.conversations_object} set state = 'closed' where conversation_id = :cid",
            {"cid": cid}
        )

    def archive_conversation(self, session_id: str) -> None:
        """Marks a conversation as 'archived'."""
        cid = self._conversation_id(session_id)
        if not cid:
            return
        self.db.execute(
            f"update {self.conversations_object} set state = 'archived' where conversation_id = :cid",
            {"cid": cid}
        )
