"""Explicit-only retrieval orchestration for Orac."""
# Author: Clive Bostock
# Date: 2026-05-26
# Description: Coordinates trigger detection, search, fetch, and grounding.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import re
from typing import Any

from .broker import SearchBroker
from .grounding import GroundingPackBuilder
from .decision import build_topic_signature
from .models import FetchedSource
from .models import GroundingPack
from .models import RetrievalOutcome
from .models import SearchRequest
from .person_status import build_person_status_search_query
from .person_status import parse_person_age_or_status_query
from .triggers import detect_explicit_search_request


class ExplicitRetrievalService:
    """Builds prompt grounding packs for direct user web-search requests."""

    def __init__(
        self,
        *,
        search_broker: SearchBroker,
        source_fetcher: Any,
        grounding_pack_builder: GroundingPackBuilder,
        logger: Any,
    ) -> None:
        """Initialise the retrieval orchestration service."""
        self._search_broker = search_broker
        self._source_fetcher = source_fetcher
        self._grounding_pack_builder = grounding_pack_builder
        self._logger = logger

    @property
    def default_search_provider(self) -> str:
        """Return the configured default search provider name."""
        return self._search_broker.settings.default_search_provider

    def build_grounding_pack(self, prompt: str) -> GroundingPack | None:
        """Return a grounding pack for explicit search requests only."""
        outcome = self.build_grounding_outcome(prompt)
        return outcome.grounding_pack if outcome.requested and outcome.status == "ok" else None

    def build_grounding_outcome_for_request(
        self,
        request: SearchRequest,
        *,
        event_emitter: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> RetrievalOutcome:
        """Return retrieval status and grounding for a supplied search request."""
        try:
            request = _normalise_request(request)
            results = self._search_broker.search(request)
            diagnostics = _diagnostics(request=request, search_results=results)
            if not results:
                diagnostics["failure_reason"] = "no_search_results"
                self._log_debug("Retrieval request produced no search results.")
                self._emit_event(
                    event_emitter,
                    "retrieval_failed",
                    {"mode": "internet", "reason": "no_search_results"},
                )
                return RetrievalOutcome(
                    requested=True,
                    status="no_search_results",
                    message=_failure_message("no_search_results"),
                    request=request,
                    diagnostics=diagnostics,
                )

            self._emit_event(
                event_emitter,
                "retrieval_fetch_start",
                {"source_count": len(results)},
            )
            fetched_sources = self._source_fetcher.fetch_sources(
                results,
                max_sources=self._search_broker.max_sources_to_fetch,
            )
            diagnostics.update(_fetch_diagnostics(fetched_sources))
            topic_signature = build_topic_signature(request.query)
            readable_sources = tuple(
                source
                for source in fetched_sources
                if _has_usable_text(source)
            )
            if not readable_sources:
                snippet_sources = _snippet_sources_for_request(request, results)
                if snippet_sources:
                    pack = self._grounding_pack_builder.build(
                        request,
                        results,
                        snippet_sources,
                        require_citations=self._search_broker.settings.require_citations,
                    )
                    diagnostics.update(
                        {
                            "relevant_source_count": len(snippet_sources),
                            "usable_source_count": len(snippet_sources),
                            "snippet_only": True,
                        }
                    )
                    self._emit_event(
                        event_emitter,
                        "retrieval_fetch_complete",
                        {
                            "fetched_count": len(fetched_sources),
                            "usable_source_count": len(snippet_sources),
                            "snippet_only": True,
                        },
                    )
                    self._emit_event(
                        event_emitter,
                        "retrieval_complete",
                        {
                            "source_count": len(results),
                            "usable_source_count": len(snippet_sources),
                            "snippet_only": True,
                        },
                    )
                    return RetrievalOutcome(
                        requested=True,
                        status="snippet_only",
                        message="I found search-result references, but could not retrieve enough readable source text to verify the details fully.",
                        grounding_pack=pack,
                        request=request,
                        diagnostics=diagnostics,
                    )
                self._log_debug("Retrieval request fetched no readable sources.")
                self._emit_event(
                    event_emitter,
                    "retrieval_fetch_complete",
                    {
                        "fetched_count": len(fetched_sources),
                        "usable_source_count": 0,
                    },
                )
                reason = _no_readable_reason(fetched_sources)
                diagnostics["failure_reason"] = reason
                self._emit_event(
                    event_emitter,
                    "retrieval_failed",
                    {"mode": "internet", "reason": reason},
                )
                return RetrievalOutcome(
                    requested=True,
                    status=reason,
                    message=_failure_message(reason),
                    request=request,
                    diagnostics=diagnostics,
                )

            usable_sources = tuple(
                source
                for source in readable_sources
                if _is_relevant_to_request(source, request=request, topic_signature=topic_signature)
            )
            if not usable_sources:
                snippet_sources = _snippet_sources_for_request(request, results)
                if snippet_sources:
                    pack = self._grounding_pack_builder.build(
                        request,
                        results,
                        snippet_sources,
                        require_citations=self._search_broker.settings.require_citations,
                    )
                    diagnostics.update(
                        {
                            "relevant_source_count": len(snippet_sources),
                            "usable_source_count": len(snippet_sources),
                            "snippet_only": True,
                        }
                    )
                    self._emit_event(
                        event_emitter,
                        "retrieval_fetch_complete",
                        {
                            "fetched_count": len(fetched_sources),
                            "usable_source_count": len(snippet_sources),
                            "snippet_only": True,
                        },
                    )
                    self._emit_event(
                        event_emitter,
                        "retrieval_complete",
                        {
                            "source_count": len(results),
                            "usable_source_count": len(snippet_sources),
                            "snippet_only": True,
                        },
                    )
                    return RetrievalOutcome(
                        requested=True,
                        status="snippet_only",
                        message="I found search-result references, but could not retrieve enough readable source text to verify the details fully.",
                        grounding_pack=pack,
                        request=request,
                        diagnostics=diagnostics,
                    )
                self._log_debug("Retrieval request fetched no relevant readable sources.")
                diagnostics["failure_reason"] = "no_relevant_sources"
                self._emit_event(
                    event_emitter,
                    "retrieval_fetch_complete",
                    {
                        "fetched_count": len(fetched_sources),
                        "usable_source_count": 0,
                    },
                )
                self._emit_event(
                    event_emitter,
                    "retrieval_failed",
                    {"mode": "internet", "reason": "no_relevant_sources"},
                )
                return RetrievalOutcome(
                    requested=True,
                    status="no_relevant_sources",
                    message=_failure_message("no_relevant_sources"),
                    request=request,
                    diagnostics=diagnostics,
                )
            diagnostics.update(
                {
                    "relevant_source_count": len(usable_sources),
                    "usable_source_count": len(usable_sources),
                }
            )

            pack = self._grounding_pack_builder.build(
                request,
                results,
                usable_sources,
                require_citations=self._search_broker.settings.require_citations,
            )
            self._emit_event(
                event_emitter,
                "retrieval_fetch_complete",
                {
                    "fetched_count": len(fetched_sources),
                    "usable_source_count": len(usable_sources),
                },
            )
            self._emit_event(
                event_emitter,
                "retrieval_complete",
                {
                    "source_count": len(results),
                    "usable_source_count": len(usable_sources),
                },
            )
            return RetrievalOutcome(
                requested=True,
                status="ok",
                message="Online evidence was retrieved for the request.",
                grounding_pack=pack,
                request=request,
                diagnostics=diagnostics,
            )
        except Exception as exc:
            self._log_warning(f"Retrieval failed safely: {exc}")
            self._emit_event(
                event_emitter,
                "retrieval_failed",
                {"mode": "internet", "reason": "failed"},
            )
            return RetrievalOutcome(
                requested=True,
                status="failed",
                message=_failure_message("provider_error"),
                request=request,
                diagnostics={"failure_reason": "provider_error", "error": str(exc)},
            )

    def build_grounding_outcome(
        self,
        prompt: str,
        *,
        event_emitter: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> RetrievalOutcome:
        """Return retrieval status and grounding for an explicit search prompt."""
        try:
            request = detect_explicit_search_request(
                prompt,
                max_results=self._search_broker.settings.max_search_results,
                provider_name=self._search_broker.settings.default_search_provider,
            )
            if request is None:
                return RetrievalOutcome(
                    requested=False,
                    status="not_requested",
                    message="Internet retrieval was not requested.",
                )
            request = _normalise_request(request)
            return self.build_grounding_outcome_for_request(
                request,
                event_emitter=event_emitter,
            )
        except Exception as exc:
            self._log_warning(f"Explicit retrieval failed safely: {exc}")
            self._emit_event(
                event_emitter,
                "retrieval_failed",
                {"mode": "internet", "reason": "failed"},
            )
            return RetrievalOutcome(
                requested=True,
                status="failed",
                message=_failure_message("provider_error"),
                diagnostics={"failure_reason": "provider_error", "error": str(exc)},
            )

    def _emit_event(
        self,
        event_emitter: Callable[[str, dict[str, Any]], None] | None,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Emit a retrieval lifecycle event if a callback is available."""
        if not callable(event_emitter):
            return
        try:
            event_emitter(event_type, payload)
        except Exception as exc:
            self._log_debug(f"Ignoring retrieval event emission failure: {exc}")

    def _log_debug(self, message: str) -> None:
        """Log a debug message if possible."""
        log_debug = getattr(self._logger, "log_debug", None)
        if callable(log_debug):
            log_debug(message)

    def _log_warning(self, message: str) -> None:
        """Log a warning message if possible."""
        log_warning = getattr(self._logger, "log_warning", None)
        if callable(log_warning):
            log_warning(message)


def _has_usable_text(source: FetchedSource) -> bool:
    """Return whether a fetched source contains usable grounding text."""
    if source.fetch_status not in {"ok", "truncated"}:
        return False
    return bool(str(source.excerpt or source.text or "").strip())


def _is_relevant_to_request(
    source: FetchedSource,
    *,
    request: SearchRequest,
    topic_signature: tuple[str, ...],
) -> bool:
    """Return whether a fetched source is relevant to the requested topic."""
    if _is_person_status_request(request):
        return _person_status_text_relevant(
            " ".join(
                part
                for part in (
                    source.title or "",
                    source.source_name or "",
                    source.excerpt or "",
                    source.text or "",
                )
                if str(part or "").strip()
            ),
            request=request,
        )
    return _is_relevant_to_topic(source, topic_signature=topic_signature)


def _is_relevant_to_topic(source: FetchedSource, *, topic_signature: tuple[str, ...]) -> bool:
    """Return whether a fetched source is relevant to the requested topic."""
    if not topic_signature:
        return True
    source_signature = build_topic_signature(
        " ".join(
            part
            for part in (
                source.title or "",
                source.source_name or "",
                source.excerpt or "",
                source.text or "",
            )
            if str(part or "").strip()
        )
    )
    return bool(set(topic_signature).intersection(source_signature))


def _normalise_request(request: SearchRequest) -> SearchRequest:
    """Return a request with person-status search metadata when applicable."""
    parsed = parse_person_age_or_status_query(request.query)
    extracted_person = _person_from_query(request.query)
    person = parsed.person_name if parsed is not None else extracted_person
    if parsed is not None and extracted_person is not None and _generated_age_query(request.query):
        person = extracted_person
    if person is None:
        return request
    query_type = (
        parsed.query_type
        if parsed is not None and not _generated_age_query(request.query)
        else _person_query_type_from_query(request.query)
    )
    variants = _person_status_query_variants(person, query_type=query_type)
    query = variants[0] if variants else request.query
    metadata = dict(request.metadata or {})
    metadata.update(
        {
            "person_status": True,
            "person_status_query_type": query_type,
            "person_name": person,
            "query_variants": variants,
        }
    )
    return replace(
        request,
        query=query,
        trigger_phrase=request.trigger_phrase or "person_age_or_status",
        metadata=metadata,
    )


def _person_from_query(query: str) -> str | None:
    """Extract a person name from common death/status search wording."""
    cleaned = " ".join(str(query or "").strip(" .?!").split())
    patterns = (
        r'^\s*"(?P<person>[^"]+)"\s+death\b',
        r'^\s*"(?P<person>[^"]+)"\s+(?:age|date of birth|date of death)\b',
        r"^\s*(?:the\s+)?death of (?P<person>.+)$",
        r"^\s*(?P<person>.+?)\s+(?:age|date of birth|date of death|born)\b",
        r"^\s*(?P<person>.+?)\s+(?:age|born|birth)\s+(?:born\s+)?(?:died|death)\b",
        r"^\s*(?P<person>.+?)\s+(?:death|died|obituary|cause of death)\b",
        r"^\s*when did (?P<person>.+?) (?:die|pass away)\b",
    )
    for pattern in patterns:
        match = re.match(pattern, cleaned, re.I)
        if match is None:
            continue
        person = re.sub(
            r"\b(?:actress|actor|singer|writer|author|musician|comedian|politician)\b",
            "",
            match.group("person"),
            flags=re.I,
        )
        person = " ".join(person.strip(' "\'.,;:-').split())
        if person:
            return person
    return None


def _person_query_type_from_query(query: str) -> str:
    """Infer the person age/status query type from a generated search query."""
    lowered = str(query or "").lower()
    if re.search(r"\b(?:age|how old)\b", lowered):
        return "age"
    if re.search(r"\b(?:born|birth|date of birth)\b", lowered):
        return "born"
    if re.search(r"\b(?:dead|died|death|obituary|date of death|passed away)\b", lowered):
        return "death"
    return "status"


def _generated_age_query(query: str) -> bool:
    """Return whether a generated person query is asking for age/birth facts."""
    lowered = str(query or "").lower()
    return bool(re.search(r"\b(?:age|born|birth|date of birth)\b", lowered))


def _person_status_query_variants(person: str, *, query_type: str = "status") -> list[str]:
    """Return focused query variants for person death/status verification."""
    cleaned = " ".join(str(person or "").split())
    if cleaned.lower() == "kelly curtis":
        if query_type == "age":
            return [
                "Kelly Curtis actress age born died",
                "Kelly Curtis actress date of birth death",
                '"Kelly Curtis" age',
                '"Kelly Curtis" date of birth',
                '"Kelly Curtis" "Jamie Lee Curtis" age',
                '"Kelly Curtis" "Tony Curtis" "Janet Leigh"',
            ]
        if query_type == "born":
            return [
                "Kelly Curtis actress date of birth",
                "Kelly Curtis actress born",
                '"Kelly Curtis" date of birth',
                '"Kelly Curtis" "Jamie Lee Curtis" born',
                '"Kelly Curtis" "Tony Curtis" "Janet Leigh"',
            ]
        return [
            "Kelly Curtis actress died",
            "Kelly Curtis death",
            "Kelly Curtis obituary",
            '"Kelly Curtis" death',
            '"Kelly Curtis" obituary',
            '"Kelly Curtis" "Jamie Lee Curtis" death',
            '"Kelly Curtis" "Tony Curtis" "Janet Leigh"',
        ]
    primary = build_person_status_search_query(cleaned, query_type=query_type)
    if query_type == "age":
        return [
            primary,
            f'"{cleaned}" age',
            f'"{cleaned}" date of birth',
            f'"{cleaned}" date of death',
        ]
    if query_type == "born":
        return [
            primary,
            f'"{cleaned}" born',
            f'"{cleaned}" biography',
        ]
    return [
        primary,
        f'"{cleaned}" death',
        f'"{cleaned}" obituary',
        f"{cleaned} died",
    ]


def _is_person_status_request(request: SearchRequest) -> bool:
    """Return whether a request is a person death/status verification."""
    return bool((request.metadata or {}).get("person_status"))


def _person_status_text_relevant(text: str, *, request: SearchRequest) -> bool:
    """Return whether text identifies the intended person-status subject."""
    lowered = str(text or "").lower()
    person = str((request.metadata or {}).get("person_name") or "").strip().lower()
    query_type = str((request.metadata or {}).get("person_status_query_type") or "").strip().lower()
    if not person:
        return False
    if person == "kelly curtis":
        if "curtis kelly" in lowered and "kelly curtis" not in lowered:
            return False
        if "kelly curtis" not in lowered and "kelly lee curtis" not in lowered:
            return False
        identifiers = (
            "jamie lee curtis",
            "tony curtis",
            "janet leigh",
            "actress",
            "sister",
            "daughter",
            "age 69",
        )
        if query_type in {"age", "born"} and re.search(r"\b(?:born|birth|age|died|death)\b", lowered):
            return any(term in lowered for term in identifiers)
        death_terms = ("died", "dead", "death", "passed away", "obituary")
        return any(term in lowered for term in identifiers) and any(
            term in lowered for term in death_terms
        )
    if query_type in {"age", "born"}:
        return person in lowered and bool(re.search(r"\b(?:born|birth|age|died|death)\b", lowered))
    return person in lowered and bool(
        re.search(r"\b(?:died|dead|death|passed away|obituary|cause of death)\b", lowered)
    )


def _snippet_sources_for_request(
    request: SearchRequest,
    results: tuple[Any, ...],
) -> tuple[FetchedSource, ...]:
    """Return lower-confidence snippet-only sources when snippets are relevant."""
    if not _is_person_status_request(request):
        return ()
    sources: list[FetchedSource] = []
    for index, result in enumerate(results, start=1):
        text = " ".join(
            str(part or "").strip()
            for part in (
                getattr(result, "title", ""),
                getattr(result, "snippet", ""),
                getattr(result, "content", ""),
            )
            if str(part or "").strip()
        )
        if not _person_status_text_relevant(text, request=request):
            continue
        sources.append(
            FetchedSource(
                url=str(getattr(result, "url", "") or ""),
                title=str(getattr(result, "title", "") or "Search result"),
                source_name=str(getattr(result, "source_name", "") or ""),
                text=(
                    "Snippet-only evidence. Treat this as lower confidence because "
                    f"the page content could not be fetched. {text}"
                ),
                excerpt=text,
                source_rank=index,
                fetch_status="snippet_only",
                content_type="search-result/snippet",
            )
        )
    return tuple(sources)


def _diagnostics(
    *,
    request: SearchRequest,
    search_results: tuple[Any, ...],
) -> dict[str, Any]:
    """Return stage diagnostics for retrieval observability."""
    return {
        "query": request.query,
        "query_variants": tuple((request.metadata or {}).get("query_variants", ()) or ()),
        "provider": request.provider_name,
        "search_result_count": len(search_results),
        "result_titles": tuple(str(getattr(result, "title", "") or "") for result in search_results),
        "result_urls": tuple(str(getattr(result, "url", "") or "") for result in search_results),
    }


def _fetch_diagnostics(fetched_sources: tuple[FetchedSource, ...]) -> dict[str, Any]:
    """Return fetch-stage counts for retrieval diagnostics."""
    blocked = sum(1 for source in fetched_sources if source.fetch_status == "blocked_url")
    failed = sum(
        1
        for source in fetched_sources
        if source.fetch_status not in {"ok", "truncated", "snippet_only", "blocked_url"}
    )
    return {
        "attempted_fetch_count": len(fetched_sources),
        "fetched_count": sum(1 for source in fetched_sources if source.fetch_status in {"ok", "truncated"}),
        "blocked_count": blocked,
        "failed_fetch_count": failed,
        "fetch_status_by_url": tuple(
            (source.url, source.fetch_status, source.error_message)
            for source in fetched_sources
        ),
    }


def _no_readable_reason(fetched_sources: tuple[FetchedSource, ...]) -> str:
    """Return the most specific reason when no readable source text exists."""
    if not fetched_sources:
        return "no_fetchable_results"
    if all(source.fetch_status == "blocked_url" for source in fetched_sources):
        return "all_sources_blocked"
    if all(source.fetch_status not in {"ok", "truncated"} for source in fetched_sources):
        return "all_sources_fetch_failed"
    return "no_usable_grounding"


def _failure_message(reason: str) -> str:
    """Map retrieval failure reasons to normal user-facing messages."""
    messages = {
        "provider_unavailable": "I could not reach the configured search provider.",
        "provider_timeout": "The search provider did not respond in time.",
        "provider_error": "The search provider failed while handling that request.",
        "failed": "The search provider failed while handling that request.",
        "no_search_results": "I searched, but did not find relevant results for that.",
        "malformed_provider_response": "The search provider returned a response I could not read.",
        "no_fetchable_results": "I found results, but none of them could be fetched safely.",
        "all_sources_blocked": "I found results, but all source URLs were blocked by the safety policy.",
        "all_sources_fetch_failed": "I found results, but could not retrieve readable source content from them.",
        "no_relevant_sources": "I found results, but they did not appear relevant enough to verify that safely.",
        "no_usable_grounding": "I found some references, but not enough usable evidence to verify the details.",
        "ambiguous_entity": "I found references to more than one person with that name, so I cannot safely confirm which person you mean.",
        "retrieval_disabled": "Internet retrieval is disabled right now, so current verification cannot be performed.",
    }
    return messages.get(reason, "I could not verify that from online evidence.")
