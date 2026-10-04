"""Persist and claim durable conversation-title requests."""

# Author: Clive Bostock
# Date: 04-Oct-2026
# Description: Calls the least-privilege ORAC_CODE conversation title API.

from __future__ import annotations

from typing import Any, Callable

from orac_core.knowledge.repository import default_orac_session


class ConversationTitleRepository:
    """Thin runtime wrapper around ``conversation_title_api``."""

    _PACKAGE = "orac_code.conversation_title_api"

    def __init__(self, session_factory: Callable[[], Any] | None = None) -> None:
        """Initialise with an injectable runtime session factory."""
        self._session_factory = session_factory or default_orac_session

    def claim(self, *, owner_id: str, lease_seconds: int) -> dict[str, Any] | None:
        """Claim and return the next eligible title request."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                request_id = cursor.callfunc(
                    f"{self._PACKAGE}.try_claim_next_request",
                    int,
                    [owner_id, lease_seconds],
                )
                session.commit()
                if request_id is None:
                    return None
                cursor.execute(
                    """
                    select title_request_id, conversation_id, lease_token, attempts
                      from orac_code.conversation_title_requests_v
                     where title_request_id = :request_id
                    """,
                    {"request_id": int(request_id)},
                )
                row = cursor.fetchone()
                if row is None:
                    return None
                columns = [item[0].lower() for item in cursor.description]
                return dict(zip(columns, row, strict=True))
        finally:
            _close_quietly(session)

    def dialogue(self, conversation_id: int, *, limit: int = 8) -> list[dict[str, str]]:
        """Return bounded recent user/assistant dialogue for title generation."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                cursor.execute(
                    """
                    select role, content_text
                      from (
                        select role, content_text, turn_index
                          from orac_code.conversation_title_dialogue_v
                         where conversation_id = :conversation_id
                           and role in ('user', 'assistant')
                         order by turn_index desc
                      )
                     where rownum <= :row_limit
                     order by turn_index
                    """,
                    {"conversation_id": int(conversation_id), "row_limit": int(limit)},
                )
                return [
                    {"role": str(role), "content": str(content or "")}
                    for role, content in cursor.fetchall()
                ]
        finally:
            _close_quietly(session)

    def complete(
        self, *, request_id: int, owner_id: str, lease_token: str, title: str
    ) -> None:
        """Store a title only if the conversation remains untitled."""
        self._call("complete_request", [request_id, owner_id, lease_token, title])

    def fail(
        self,
        *,
        request_id: int,
        owner_id: str,
        lease_token: str,
        message: str,
        retryable: bool,
    ) -> None:
        """Record a bounded retryable or terminal failure."""
        self._call(
            "fail_request",
            [request_id, owner_id, lease_token, message[:1000], "Y" if retryable else "N"],
        )

    def _call(self, name: str, arguments: list[Any]) -> None:
        """Call and commit one title API procedure."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                cursor.callproc(f"{self._PACKAGE}.{name}", arguments)
            session.commit()
        finally:
            _close_quietly(session)


def _close_quietly(session: Any) -> None:
    """Close a repository session without masking the operation result."""
    try:
        session.close()
    except Exception:
        pass
