"""Host-owned, scope-bound project retrieval for external read-only adapters."""
# Author: Clive Bostock
# Date: 11-Oct-2026
# Description: Reuses Core retrieval while binding project, identity, and current evidence.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import json
import secrets
import threading
import time
from typing import Callable

from orac_core.governed_retrieval.discovery import AuthorisedKnowledgeDomainRepository

from .models import KnowledgeSearchResult
from .retrieval import KnowledgeRetrievalService
from .scope import KnowledgeScope


MAX_QUERY_CHARS = 2048
MAX_RESULTS = 6
MAX_PREVIEW_CHARS = 500
MAX_FETCH_CHARS = 2200
MAX_CALLS_PER_MINUTE = 30
MAX_CONCURRENT_CALLS = 2
SEARCH_TICKET_SECONDS = 300
MAX_TICKETS = 256
PROJECT_PAGE_SIZE = 25
PROJECT_CATALOGUE_LIMIT = 4096


class ProjectRetrievalDenied(PermissionError):
    """Raised when a bridge cannot safely return current evidence."""


@dataclass(frozen=True, slots=True)
class ProjectEvidence:
    """One bounded current chunk with an opaque fetch reference."""

    reference: str
    project_code: str
    document_id: int
    document_version_id: int
    chunk_id: int
    page_start: int | None
    page_end: int | None
    text: str


@dataclass(frozen=True, slots=True)
class ProjectDescriptor:
    """One bounded, currently authorised project descriptor."""

    project_code: str
    display_name: str
    description: str


@dataclass(frozen=True, slots=True)
class ProjectPage:
    """One page of project descriptors with a fresh-query continuation offset."""

    projects: tuple[ProjectDescriptor, ...]
    next_offset: int | None


@dataclass(frozen=True, slots=True)
class _Ticket:
    principal: str
    query: str
    project_code: str
    document_id: int
    document_version_id: int
    chunk_id: int
    classification_tags: tuple[str, ...]
    expires_at: float


class CoreProjectRetrievalBridge:
    """Expose authorised projects through Core-owned discovery and retrieval."""

    def __init__(
        self,
        *,
        project_code: str | None,
        allowed_classifications: frozenset[str],
        retrieval_service: KnowledgeRetrievalService,
        project_repository: AuthorisedKnowledgeDomainRepository,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialise a fail-closed bridge with an optional administrator limit."""
        if (
            (
                project_code is not None
                and (not project_code or len(project_code) > 100 or project_code == "*")
            )
            or not allowed_classifications
            or any(
                not code or len(code) > 100 or code == "*"
                for code in allowed_classifications
            )
        ):
            raise ValueError("Project or classification restriction is invalid.")
        self._restricted_project = project_code
        self._allowed_classifications = frozenset(allowed_classifications)
        self._retrieval = retrieval_service
        self._projects = project_repository
        self._clock = clock
        self._lock = threading.Lock()
        self._recent_calls: dict[str, deque[float]] = defaultdict(deque)
        self._active_calls: dict[str, int] = defaultdict(int)
        self._tickets: dict[str, _Ticket] = {}

    def list_projects(self, *, principal: str, offset: int = 0) -> ProjectPage:
        """Page through a fresh Core-authorised catalogue for this principal."""
        if type(offset) is not int or not 0 <= offset <= PROJECT_CATALOGUE_LIMIT:
            raise ValueError("Project offset is invalid.")
        self._enter(principal)
        try:
            projects = self._catalogue(principal)
            page = projects[offset : offset + PROJECT_PAGE_SIZE]
            next_offset = offset + len(page)
            return ProjectPage(
                projects=page,
                next_offset=next_offset if next_offset < len(projects) else None,
            )
        finally:
            self._leave(principal)

    def search(
        self, *, principal: str, query: str, project_code: str | None = None
    ) -> tuple[ProjectEvidence, ...]:
        """Return minimal previews and references from current authorised chunks."""
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= MAX_QUERY_CHARS:
            raise ValueError("Query length is invalid.")
        if project_code is not None and (
            not isinstance(project_code, str)
            or not 1 <= len(project_code) <= 100
            or project_code == "*"
        ):
            raise ValueError("Project selection is invalid.")
        self._enter(principal)
        try:
            scope = self._selected_scope(principal, project_code)
            results = self._current_results(principal, query.strip(), scope)
            evidence: list[ProjectEvidence] = []
            with self._lock:
                self._expire_tickets()
                for item in results:
                    reference = secrets.token_urlsafe(24)
                    self._tickets[reference] = _Ticket(
                        principal=principal,
                        query=query.strip(),
                        project_code=item.scope.scope_key,
                        document_id=item.document_id,
                        document_version_id=item.document_version_id,
                        chunk_id=item.chunk_id,
                        classification_tags=item.classification_tags,
                        expires_at=self._clock() + SEARCH_TICKET_SECONDS,
                    )
                    evidence.append(self._evidence(item, reference, MAX_PREVIEW_CHARS))
                while len(self._tickets) > MAX_TICKETS:
                    self._tickets.pop(next(iter(self._tickets)))
            return tuple(evidence)
        finally:
            self._leave(principal)

    def fetch(self, *, principal: str, reference: str) -> ProjectEvidence:
        """Rerun Core retrieval and return only the same still-current chunk."""
        if not isinstance(reference, str) or not 1 <= len(reference) <= 128:
            raise ValueError("Reference is invalid.")
        self._enter(principal)
        try:
            with self._lock:
                self._expire_tickets()
                ticket = self._tickets.get(reference)
            if ticket is None or ticket.principal != principal:
                raise ProjectRetrievalDenied("Evidence is unavailable.")
            scope = self._selected_scope(principal, ticket.project_code)
            for item in self._current_results(principal, ticket.query, scope):
                if (
                    item.document_id == ticket.document_id
                    and item.document_version_id == ticket.document_version_id
                    and item.chunk_id == ticket.chunk_id
                    and item.classification_tags == ticket.classification_tags
                ):
                    return self._evidence(item, reference, MAX_FETCH_CHARS)
            raise ProjectRetrievalDenied("Evidence is unavailable.")
        finally:
            self._leave(principal)

    def _current_results(
        self, principal: str, query: str, scope: KnowledgeScope | None
    ) -> tuple[KnowledgeSearchResult, ...]:
        if not principal or not principal.strip():
            raise ProjectRetrievalDenied("Evidence is unavailable.")
        try:
            limits = dict(
                principal_username=principal,
                max_candidate_chunks=100,
                max_selected_chunks=MAX_RESULTS,
                max_chunk_chars=MAX_FETCH_CHARS,
                max_context_chars=MAX_RESULTS * MAX_FETCH_CHARS,
            )
            if scope is None:
                outcome = self._retrieval.retrieve_authorised_projects(query, **limits)
            else:
                outcome = self._retrieval.retrieve(query, scope=scope, **limits)
        except Exception:
            raise ProjectRetrievalDenied("Evidence is unavailable.") from None
        if outcome.status == "failed" or outcome.scope != scope:
            raise ProjectRetrievalDenied("Evidence is unavailable.")
        if outcome.status == "no_evidence":
            return ()
        if outcome.status != "grounded" or len(outcome.results) > MAX_RESULTS:
            raise ProjectRetrievalDenied("Evidence is unavailable.")
        return tuple(item for item in outcome.results if self._visible(item, scope))

    def _visible(
        self, item: KnowledgeSearchResult, scope: KnowledgeScope | None
    ) -> bool:
        return (
            item.scope.scope_type == "PROJECT"
            and (scope is None or item.scope == scope)
            and bool(item.classification_tags)
            and set(item.classification_tags).issubset(self._allowed_classifications)
        )

    def _selected_scope(
        self, principal: str, project_code: str | None
    ) -> KnowledgeScope | None:
        """Check the live catalogue before accepting a project selector."""
        if self._restricted_project is not None:
            if project_code is not None and project_code != self._restricted_project:
                raise ProjectRetrievalDenied("Evidence is unavailable.")
            project_code = self._restricted_project
        if project_code is None:
            self._catalogue(principal)
            return None
        if not any(
            item.project_code == project_code for item in self._catalogue(principal)
        ):
            raise ProjectRetrievalDenied("Evidence is unavailable.")
        return KnowledgeScope("PROJECT", project_code)

    def _catalogue(self, principal: str) -> tuple[ProjectDescriptor, ...]:
        """Read Core's current catalogue and reject incomplete or malformed data."""
        if not isinstance(principal, str) or not principal.strip():
            raise ProjectRetrievalDenied("Evidence is unavailable.")
        try:
            rows = self._projects.load_authorised_projects(
                principal, PROJECT_CATALOGUE_LIMIT + 1
            )
            if len(rows) > PROJECT_CATALOGUE_LIMIT or any(
                int(row["authorised_catalogue_size"]) != len(rows) for row in rows
            ):
                raise ProjectRetrievalDenied("Project catalogue is unavailable.")
            projects = []
            seen = set()
            for row in rows:
                code = str(row["project_code"]).strip()
                if not code or len(code) > 100 or code in seen:
                    raise ValueError("Invalid project catalogue")
                seen.add(code)
                if self._restricted_project is None or code == self._restricted_project:
                    projects.append(
                        ProjectDescriptor(
                            project_code=code,
                            display_name=str(row.get("display_name") or code).strip()[
                                :200
                            ],
                            description=str(row.get("description") or "").strip()[:500],
                        )
                    )
            return tuple(projects)
        except ProjectRetrievalDenied:
            raise
        except Exception:
            raise ProjectRetrievalDenied("Project catalogue is unavailable.") from None

    @staticmethod
    def _evidence(
        item: KnowledgeSearchResult, reference: str, limit: int
    ) -> ProjectEvidence:
        page_start, page_end = CoreProjectRetrievalBridge._page_range(
            item.chunk_metadata_json
        )
        return ProjectEvidence(
            reference=reference,
            project_code=item.scope.scope_key,
            document_id=item.document_id,
            document_version_id=item.document_version_id,
            chunk_id=item.chunk_id,
            page_start=page_start,
            page_end=page_end,
            text=item.chunk_text[:limit],
        )

    @staticmethod
    def _page_range(metadata_json: str | None) -> tuple[int | None, int | None]:
        """Expose only validated page coordinates from existing chunk metadata."""
        if not metadata_json:
            return None, None
        try:
            metadata = json.loads(metadata_json)
        except (TypeError, ValueError):
            return None, None
        if not isinstance(metadata, dict):
            return None, None
        start = metadata.get("page_start", metadata.get("page_number"))
        end = metadata.get("page_end", start)
        if type(start) is not int or type(end) is not int or start < 1 or end < start:
            return None, None
        return start, end

    def _enter(self, principal: str) -> None:
        if not isinstance(principal, str) or not principal.strip():
            raise ProjectRetrievalDenied("Evidence is unavailable.")
        now = self._clock()
        with self._lock:
            recent = self._recent_calls[principal]
            while recent and recent[0] <= now - 60:
                recent.popleft()
            if (
                len(recent) >= MAX_CALLS_PER_MINUTE
                or self._active_calls[principal] >= MAX_CONCURRENT_CALLS
            ):
                raise ProjectRetrievalDenied("Retrieval limit reached.")
            recent.append(now)
            self._active_calls[principal] += 1

    def _leave(self, principal: str) -> None:
        with self._lock:
            self._active_calls[principal] -= 1

    def _expire_tickets(self) -> None:
        now = self._clock()
        for reference, ticket in tuple(self._tickets.items()):
            if ticket.expires_at <= now:
                del self._tickets[reference]
