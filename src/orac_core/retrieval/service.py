"""Explicit-only retrieval orchestration for Orac."""
# Author: Clive Bostock
# Date: 2026-05-26
# Description: Coordinates trigger detection, search, fetch, and grounding.

from __future__ import annotations

from typing import Any

from .broker import SearchBroker
from .grounding import GroundingPackBuilder
from .models import FetchedSource
from .models import GroundingPack
from .models import RetrievalOutcome
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

    def build_grounding_pack(self, prompt: str) -> GroundingPack | None:
        """Return a grounding pack for explicit search requests only."""
        outcome = self.build_grounding_outcome(prompt)
        return outcome.grounding_pack if outcome.requested and outcome.status == "ok" else None

    def build_grounding_outcome(self, prompt: str) -> RetrievalOutcome:
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
                    message="The user did not explicitly request internet retrieval.",
                )

            results = self._search_broker.search(request)
            if not results:
                self._log_debug("Explicit retrieval produced no search results.")
                return RetrievalOutcome(
                    requested=True,
                    status="no_search_results",
                    message="I could not retrieve online evidence for that request.",
                    request=request,
                )

            fetched_sources = self._source_fetcher.fetch_sources(
                results,
                max_sources=self._search_broker.max_sources_to_fetch,
            )
            usable_sources = tuple(
                source for source in fetched_sources if _has_usable_text(source)
            )
            if not usable_sources:
                self._log_debug("Explicit retrieval fetched no readable sources.")
                return RetrievalOutcome(
                    requested=True,
                    status="no_usable_sources",
                    message="I could not retrieve readable online evidence for that request.",
                    request=request,
                )

            pack = self._grounding_pack_builder.build(
                request,
                results,
                usable_sources,
                require_citations=self._search_broker.settings.require_citations,
            )
            return RetrievalOutcome(
                requested=True,
                status="ok",
                message="Online evidence was retrieved for the explicit request.",
                grounding_pack=pack,
                request=request,
            )
        except Exception as exc:
            self._log_warning(f"Explicit retrieval failed safely: {exc}")
            return RetrievalOutcome(
                requested=True,
                status="failed",
                message="I could not retrieve online evidence for that request.",
            )

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
