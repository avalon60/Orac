# model/context_manager.py
from __future__ import annotations

from typing import Optional, List, Dict, Any
import json
import time

import oracledb  # for error code inspection
from lib.session_manager import DBSession  # <- your DBSession wrapper


class OracContextManager:
    """
    Minimal Oracle-backed context manager for Orac:
      - Resolves/creates user by username
      - Resolves/creates conversation by session_id (unique)
      - Appends messages with safe turn_index (retries on ORA-00001)
      - Loads/prunes/deletes conversation context
    """

    def __init__(self, db: DBSession):
        self.db = db

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_or_create_user(self, username: str) -> int:
        norm = username.strip()
        rows = self.db.dict_sql_dataset(
            "select user_id from orac.users where username = :u",
            {"u": norm}
        )
        if rows:
            return int(rows[0]["USER_ID"])

        with self.db.cursor() as cur:
            out_id = cur.var(oracledb.NUMBER)
            cur.execute(
                "insert into orac.users(username, is_active) "
                "values(:1, 'y') returning user_id into :2",
                [norm, out_id]
            )
            self.db.commit()
            val = out_id.getvalue()
            return int(val[0]) if isinstance(val, list) else int(val)

    def _get_or_create_conversation(self, user_id: int, session_id: str,
                                    llm_id: Optional[int]) -> int:
        rows = self.db.dict_sql_dataset(
            "select conversation_id from orac.conversations where session_id = :s",
            {"s": session_id}
        )
        if rows:
            return int(rows[0]["CONVERSATION_ID"])

        with self.db.cursor() as cur:
            out_id = cur.var(oracledb.NUMBER)
            # positional binds throughout (avoid mixing named+positional)
            cur.execute(
                "insert into orac.conversations(user_id, session_id, llm_id, state) "
                "values(:1, :2, :3, 'open') returning conversation_id into :4",
                [user_id, session_id, llm_id, out_id]
            )
            self.db.commit()
            val = out_id.getvalue()
            return int(val[0]) if isinstance(val, list) else int(val)

    # -------------------------------------------------------------------------
    # Timeout-aware conversation handling
    # -------------------------------------------------------------------------

    def _last_activity_utc(self, conversation_id: int) -> float:
        """
        Returns the last activity epoch seconds for a conversation,
        based on the latest message.created_on. Falls back to 'now' if none.
        """
        rows = self.db.fetch_as_lists(
            "select max(created_on) from orac.messages where conversation_id = :cid",
            {"cid": conversation_id}
        )
        if rows and rows[0][0]:
            # rows[0][0] is a datetime; convert to epoch
            dt = rows[0][0]
            try:
                return dt.timestamp()
            except Exception:
                pass
        # No messages yet; treat as 'now' so we don't roll over immediately
        import time as _t
        return _t.time()

    def ensure_conversation_with_timeout(
        self, *,
        user_name: str,
        session_id_base: str,
        llm_id: Optional[int],
        timeout_seconds: int
    ) -> Dict[str, Any]:
        """
        Ensures there is a conversation for session_id_base, but rolls over to a NEW
        conversation (with a suffixed session_id) if the last activity exceeds timeout_seconds.

        Returns: { "conversation_id": int, "session_id": str, "rolled_over": bool }
        """
        # First: if an exact session_id exists, consider timeout
        rows = self.db.dict_sql_dataset(
            "select conversation_id from orac.conversations where session_id = :s",
            {"s": session_id_base}
        )
        if rows:
            conv_id = int(rows[0]["CONVERSATION_ID"])
            last_ts = self._last_activity_utc(conv_id)
            import time as _t
            age = _t.time() - last_ts
            if timeout_seconds > 0 and age >= timeout_seconds:
                # Rollover: create a brand-new conversation with a suffixed session_id
                suffix = int(_t.time())
                new_sid = f"{session_id_base}#{suffix}"
                new_cid = self.ensure_conversation(user_name=user_name, session_id=new_sid, llm_id=llm_id)
                return {"conversation_id": new_cid, "session_id": new_sid, "rolled_over": True}
            else:
                # Keep using the existing one
                return {"conversation_id": conv_id, "session_id": session_id_base, "rolled_over": False}

        # No exact match: just create the canonical (base) session_id conversation
        conv_id = self.ensure_conversation(user_name=user_name, session_id=session_id_base, llm_id=llm_id)
        return {"conversation_id": conv_id, "session_id": session_id_base, "rolled_over": False}


    def _conversation_id(self, session_id: str) -> Optional[int]:
        rows = self.db.dict_sql_dataset(
            "select conversation_id from orac.conversations where session_id = :s",
            {"s": session_id}
            )
        return int(rows[0]["CONVERSATION_ID"]) if rows else None

    def _next_turn_index(self, conversation_id: int) -> int:
        rows = self.db.fetch_as_lists(
            "select nvl(max(turn_index),0)+1 from orac.messages where conversation_id = :cid",
            {"cid": conversation_id}
        )
        return int(rows[0][0]) if rows else 1

    def get_conversation_title(self, session_id: str) -> Optional[str]:
        """Returns the current title for a conversation, or None if missing."""
        cid = self._conversation_id(session_id)
        if not cid:
            return None
        rows = self.db.fetch_as_lists(
            "select title from orac.conversations where conversation_id = :cid",
            {"cid": cid}
        )
        if not rows:
            return None
        title = rows[0][0]
        return title if isinstance(title, str) and title.strip() else None

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def ensure_conversation(self, *, user_name: str, session_id: str,
                            llm_id: Optional[int] = None) -> int:
        """Ensures user + conversation exist; returns conversation_id."""
        user_id = self._get_or_create_user(user_name)
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

        user_id = self._get_or_create_user(user_name)
        conv_id = self._get_or_create_conversation(user_id, session_id, llm_id)

        # light retry loop for (conversation_id, turn_index) unique races
        for _ in range(5):
            turn_index = self._next_turn_index(conv_id)
            try:
                with self.db.cursor() as cur:
                    out_id = cur.var(oracledb.NUMBER)
                    # full positional bind list incl. RETURNING out var
                    cur.execute(
                        "insert into orac.messages("
                        "  conversation_id, turn_index, role, content, tokens_used, meta, llm_id"
                        ") values ("
                        "  :1, :2, :3, :4, :5, :6, :7"
                        ") returning message_id into :8",
                        [
                            conv_id,
                            turn_index,
                            role,
                            content_json,  # JSON text
                            tokens_used,
                            meta_json,  # JSON text
                            llm_id,
                            out_id
                        ]
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
            "select nvl(max(turn_index),0) from orac.messages where conversation_id = :cid",
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
        lim = f"fetch first {int(limit)} rows only" if limit and limit > 0 else ""

        sql = f"""
            select turn_index, role, content, tokens_used, meta, created_on
              from orac.messages
             where conversation_id = :cid
               {role_filter}
             order by turn_index
             {lim}
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
            "select max(turn_index) from orac.messages where conversation_id = :cid",
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
                "delete from orac.messages "
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
            cur.execute("delete from orac.messages where conversation_id = :cid", {"cid": cid})
            if hard:
                cur.execute("delete from orac.conversations where conversation_id = :cid", {"cid": cid})
            else:
                cur.execute("update orac.conversations set state = 'archived' where conversation_id = :cid", {"cid": cid})
        self.db.commit()

    def set_conversation_title(self, session_id: str, title: str) -> None:
        """Sets/updates the conversation title."""
        cid = self._conversation_id(session_id)
        if not cid:
            return
        self.db.execute(
            "update orac.conversations set title = :t where conversation_id = :cid",
            {"t": title[:200], "cid": cid}
        )

    def close_conversation(self, session_id: str) -> None:
        """Marks a conversation as 'closed'."""
        cid = self._conversation_id(session_id)
        if not cid:
            return
        self.db.execute(
            "update orac.conversations set state = 'closed' where conversation_id = :cid",
            {"cid": cid}
        )

    def archive_conversation(self, session_id: str) -> None:
        """Marks a conversation as 'archived'."""
        cid = self._conversation_id(session_id)
        if not cid:
            return
        self.db.execute(
            "update orac.conversations set state = 'archived' where conversation_id = :cid",
            {"cid": cid}
        )
