"""Persist Core query lifecycle, leases and content-free audit through CODE."""

# Author: Clive Bostock
# Date: 08-Nov-2026
# Description: Least-privilege runtime adapter for relational query packages.
# Purpose: Keep queue writes outside plugin and executor connections.
# Usage: QueryRepository() uses the normal Orac service connection.
from __future__ import annotations

from dataclasses import asdict
import json
from typing import Any, Callable

import oracledb
from orac_core.knowledge.repository import default_orac_session
from .deadline import bounded_cursor, limit_session
from .models import Dataset


class QueryRepository:
    """Call only fixed worker package entrypoints as normal ORAC runtime."""

    _PACKAGE = "orac_code.relational_query_worker_api"

    def __init__(self, session_factory: Callable[[], Any] | None = None) -> None:
        """Store an injectable normal service connection factory."""
        self._factory = session_factory or (
            lambda: default_orac_session(connection_timeout_seconds=5)
        )

    def _call(self, name: str, args: list[Any]) -> None:
        session = self._factory()
        try:
            with bounded_cursor(session) as cursor:
                cursor.callproc(f"{self._PACKAGE}.{name}", args)
            limit_session(session)
            session.commit()
        finally:
            session.close()

    def sync(self, dataset: Dataset, manifest_hash: str) -> None:
        """Register declaration metadata without granting or verifying access."""
        declaration = asdict(dataset)
        declaration.pop("verified")
        self._call(
            "sync_dataset",
            [
                dataset.dataset_id,
                dataset.plugin_id,
                dataset.metadata_version,
                manifest_hash,
                json.dumps(declaration, sort_keys=True),
            ],
        )

    def available(self, dataset: Dataset, manifest_hash: str) -> bool:
        """Read current installed/enabled plugin and matching live release gate."""
        session = self._factory()
        try:
            with bounded_cursor(session) as cursor:
                return (
                    cursor.callfunc(
                        f"{self._PACKAGE}.dataset_available",
                        int,
                        [dataset.dataset_id, dataset.metadata_version, manifest_hash],
                    )
                    == 1
                )
        finally:
            session.close()

    def reviewed_metadata(self, dataset: Dataset, manifest_hash: str) -> dict[str, Any]:
        """Read only the verified projection snapshot through the fixed worker API."""
        session = self._factory()
        try:
            with bounded_cursor(session) as cursor:
                value = cursor.callfunc(
                    f"{self._PACKAGE}.reviewed_metadata",
                    oracledb.DB_TYPE_CLOB,
                    [dataset.dataset_id, dataset.metadata_version, manifest_hash],
                )
                if hasattr(value, "read"):
                    limit_session(session)
                    value = value.read(1, 131073)
                if not isinstance(value, str) or len(value.encode("utf-8")) > 131072:
                    raise ValueError("Review snapshot exceeds bound")

                def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                    result = {}
                    for name, item in pairs:
                        if name in result:
                            raise ValueError("Duplicate review field")
                        result[name] = item
                    return result

                return json.loads(value, object_pairs_hook=unique_object)
        except Exception:
            from .models import QueryDenied

            raise QueryDenied("REVIEW_METADATA_UNAVAILABLE") from None
        finally:
            session.close()

    def audit(self, event: dict[str, Any]) -> None:
        """Persist bounded metadata, excluding questions, SQL, binds and results."""
        self._call("audit_event", [json.dumps(event)])

    def claim(self, worker_id: str) -> dict[str, Any] | None:
        """Claim one immutable session-bound request and lease."""
        session = self._factory()
        try:
            with bounded_cursor(session) as cursor:
                outputs = [cursor.var(oracledb.DB_TYPE_NUMBER)] + [
                    cursor.var(oracledb.DB_TYPE_VARCHAR) for _ in range(4)
                ]
                cursor.callproc(f"{self._PACKAGE}.claim_next", [worker_id, *outputs])
                values = [output.getvalue() for output in outputs]
            limit_session(session)
            session.commit()
            return (
                dict(
                    zip(
                        ("request_id", "lease", "username", "dataset_id", "question"),
                        values,
                    )
                )
                if values[0] is not None
                else None
            )
        finally:
            session.close()

    def complete(
        self,
        request: dict[str, Any],
        worker: str,
        result: str | None,
        failure: str | None = None,
    ) -> None:
        """Complete only a current matching lease; stale completions fail closed."""
        self._call(
            "complete_query",
            [request["request_id"], worker, request["lease"], result, failure],
        )

    def purge_expired(self) -> None:
        """Remove one-day payloads and 30-day content-free audit records."""
        self._call("purge_expired", [])


class DatabaseQueryBudget:
    """Share admissions across chat, APEX and all Core runtime processes."""

    def __init__(self, repository: QueryRepository) -> None:
        """Keep the normal runtime repository and thread-local reservation tokens."""
        import threading

        self.repository = repository
        self.local = threading.local()

    def acquire(
        self, username: str, dataset_id: str, existing_id: int | None = None
    ) -> None:
        """Reserve database-wide principal/dataset capacity atomically."""
        from .models import QueryDenied

        session = self.repository._factory()
        try:
            with bounded_cursor(session) as cursor:
                token = cursor.var(oracledb.DB_TYPE_NUMBER)
                cursor.callproc(
                    f"{self.repository._PACKAGE}.reserve_query",
                    [username, dataset_id, existing_id, token],
                )
                self.local.token = token.getvalue()
            limit_session(session)
            session.commit()
        except Exception:
            raise QueryDenied("QUERY_LIMIT") from None
        finally:
            session.close()

    def release(self, username: str, dataset_id: str) -> None:
        """Release chat capacity; queue completion owns its existing lease."""
        self.repository._call("release_query", [self.local.token])
