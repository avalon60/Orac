"""Explicit-only retrieval orchestration for Orac."""
# Author: Clive Bostock
# Date: 2026-05-26
# Description: Coordinates trigger detection, search, fetch, and grounding.

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .broker import SearchBroker
from .grounding import GroundingPackBuilder
from .decision import build_topic_signature
from .models import FetchedSource
from .models import GroundingPack
from .models import RetrievalOutcome
from .models import SearchRequest
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
            results = self._search_broker.search(request)
            if not results:
                self._log_debug("Retrieval request produced no search results.")
                self._emit_event(
                    event_emitter,
                    "retrieval_failed",
                    {"mode": "internet", "reason": "no_search_results"},
                )
                return RetrievalOutcome(
                    requested=True,
                    status="no_search_results",
                    message="I could not retrieve online evidence for that request.",
                    request=request,
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
            topic_signature = build_topic_signature(request.query)
            readable_sources = tuple(
                source
                for source in fetched_sources
                if _has_usable_text(source)
            )
            if not readable_sources:
                self._log_debug("Retrieval request fetched no readable sources.")
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
                    {"mode": "internet", "reason": "no_usable_sources"},
                )
                return RetrievalOutcome(
                    requested=True,
                    status="no_usable_sources",
                    message="I could not retrieve readable online evidence for that request.",
                    request=request,
                )

            usable_sources = tuple(
                source
                for source in readable_sources
                if _is_relevant_to_topic(source, topic_signature=topic_signature)
            )
            if not usable_sources:
                self._log_debug("Retrieval request fetched no relevant readable sources.")
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
                    message="I could not find online evidence relevant to that topic.",
                    request=request,
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
                message="I could not retrieve online evidence for that request.",
                request=request,
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
                message="I could not retrieve online evidence for that request.",
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
