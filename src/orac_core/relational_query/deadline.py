"""Propagate the Core query deadline into synchronous Oracle round trips."""

# Author: Clive Bostock
# Date: 12-Nov-2026
# Description: Bound query dictionary and repository calls without changing shared sessions.
# Purpose: Prevent database waits from consuming unbounded query worker time.
# Usage: Internal Core relational query adapters use bounded_cursor(session).
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import time
from typing import Any, Iterator

from .models import QueryDenied

query_deadline: ContextVar[float | None] = ContextVar(
    "relational_query_deadline", default=None
)


def limit_session(session: Any) -> None:
    """Set each Oracle round-trip timeout to the remaining budget, at most five seconds."""
    deadline = query_deadline.get()
    remaining = 5.0 if deadline is None else min(5.0, deadline - time.monotonic())
    if remaining <= 0:
        raise QueryDenied("QUERY_TIMEOUT")
    session.call_timeout = max(1, int(remaining * 1000))


class _Cursor:
    def __init__(self, session: Any, cursor: Any) -> None:
        self.session, self.cursor = session, cursor

    def __getattr__(self, name: str) -> Any:
        value = getattr(self.cursor, name)
        if not callable(value):
            return value

        def call(*args: Any, **kwargs: Any) -> Any:
            limit_session(self.session)
            return value(*args, **kwargs)

        return call


@contextmanager
def bounded_cursor(session: Any) -> Iterator[Any]:
    """Refresh the deadline before each cursor operation on an existing session."""
    limit_session(session)
    with session.cursor() as cursor:
        yield _Cursor(session, cursor)
