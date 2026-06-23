"""Preferred biography lookup for person age and life-status queries."""
# Author: Clive Bostock
# Date: 2026-06-02
# Description: Resolves person birth, death, and age facts from Wikidata and Wikipedia.

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from datetime import date
from datetime import datetime
from typing import Any
from urllib.error import HTTPError
from urllib.error import URLError
from urllib.parse import quote
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen
import json
import re
import unicodedata

from .broker import RetrievalSettings
from .person_status import PartialDate
from .person_status import PersonBio
from .person_status import PersonStatusQuery
from .person_status import answer_from_stable_bio
from .person_status import calculate_age
from .person_status import format_partial_date
from .person_status import stable_bio_for_person

_WIKIDATA_API = "https://www.wikidata.org/w/api.php"
_WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
_WIKIPEDIA_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"
_HTTP_TIMEOUT_SECONDS = 8.0

_PERSON_DESCRIPTION_HINTS = (
    "actor",
    "actress",
    "author",
    "biologist",
    "business",
    "comedian",
    "dancer",
    "director",
    "footballer",
    "human",
    "journalist",
    "mathematician",
    "musician",
    "person",
    "politician",
    "presenter",
    "scientist",
    "singer",
    "writer",
)


@dataclass(frozen=True, slots=True)
class PersonFactResolution:
    """Describes the result of a preferred biography lookup."""

    status: str
    query: PersonStatusQuery
    answer: str | None = None
    display_name: str | None = None
    description: str = ""
    date_of_birth: PartialDate | None = None
    date_of_death: PartialDate | None = None
    cause_of_death: str | None = None
    source_kind: str = ""
    source_name: str = ""
    source_url: str = ""
    confidence: str = "low"
    search_query: str = ""
    clarification: str | None = None
    failure_message: str | None = None
    needs_generic_retrieval: bool = False
    identity_confidence: str = "low"
    identity_match_type: str = "none"
    requested_name: str = ""
    resolved_name: str = ""
    aliases_considered: tuple[str, ...] = ()
    disambiguation_required: bool = False


@dataclass(frozen=True, slots=True)
class _BiographyRecord:
    """Structured facts for one person candidate."""

    entity_id: str
    display_name: str
    description: str
    date_of_birth: PartialDate | None
    date_of_death: PartialDate | None
    cause_of_death: str | None
    aliases: tuple[str, ...]
    wikipedia_title: str | None
    source_kind: str
    source_name: str
    source_url: str
    confidence: str


@dataclass(frozen=True, slots=True)
class _IdentityMatch:
    """Identity match assessment for one biography candidate."""

    confidence: str
    match_type: str
    score: int
    aliases_considered: tuple[str, ...] = ()
    matched_alias: str | None = None
    reason: str = ""

    @property
    def allows_direct_answer(self) -> bool:
        """Return whether this identity match is strong enough to answer."""
        return self.confidence == "high"


class PersonFactResolver:
    """Resolves person biography facts using structured sources first."""

    def __init__(
        self,
        *,
        settings: RetrievalSettings,
        logger: Any | None = None,
    ) -> None:
        """Initialise the resolver."""
        self._settings = settings
        self._logger = logger

    def resolve(
        self,
        query: PersonStatusQuery,
        *,
        today: date | None = None,
    ) -> PersonFactResolution:
        """Resolve a person fact query using structured biography sources first."""
        today = today or date.today()
        query_text = (query.search_query or query.person_name or "").strip()
        fallback_resolution: PersonFactResolution | None = None
        stable_bio = stable_bio_for_person(query.person_name)

        if self._settings.prefer_wikidata:
            resolution = self._resolve_via_wikidata(query, today=today)
            if resolution is not None:
                if resolution.status == "resolved":
                    return resolution
                elif resolution.status == "ambiguous":
                    if stable_bio is not None and query.query_type != "cause":
                        answer = answer_from_stable_bio(query, today=today)
                        if answer:
                            return PersonFactResolution(
                                status="resolved",
                                query=query,
                                answer=answer,
                                display_name=stable_bio.display_name,
                                description=stable_bio.description,
                                date_of_birth=stable_bio.date_of_birth,
                                date_of_death=stable_bio.date_of_death,
                                source_kind="stable_bio",
                                source_name="Orac stable biography",
                                confidence="high",
                                search_query=query_text,
                            )
                    if not self._requires_immediate_disambiguation(resolution):
                        fallback_resolution = resolution
                        self._log_debug(
                            "Continuing biography lookup after weak Wikidata "
                            f"identity match for '{query.person_name}'."
                        )
                        resolution = None
                    else:
                        return resolution
                elif resolution is not None:
                    fallback_resolution = resolution

        if self._settings.prefer_wikipedia:
            resolution = self._resolve_via_wikipedia(query, today=today)
            if resolution is not None:
                if resolution.status == "resolved":
                    return resolution
                elif resolution.status == "ambiguous":
                    if stable_bio is not None and query.query_type != "cause":
                        answer = answer_from_stable_bio(query, today=today)
                        if answer:
                            return PersonFactResolution(
                                status="resolved",
                                query=query,
                                answer=answer,
                                display_name=stable_bio.display_name,
                                description=stable_bio.description,
                                date_of_birth=stable_bio.date_of_birth,
                                date_of_death=stable_bio.date_of_death,
                                source_kind="stable_bio",
                                source_name="Orac stable biography",
                                confidence="high",
                                search_query=query_text,
                            )
                    if not self._requires_immediate_disambiguation(resolution):
                        if fallback_resolution is None:
                            fallback_resolution = resolution
                        self._log_debug(
                            "Keeping weak Wikipedia identity match as fallback "
                            f"for '{query.person_name}'."
                        )
                        resolution = None
                    else:
                        return resolution
                elif fallback_resolution is None:
                    fallback_resolution = resolution

        if stable_bio is not None and query.query_type != "cause":
            answer = answer_from_stable_bio(query, today=today)
            if answer:
                return PersonFactResolution(
                    status="resolved",
                    query=query,
                    answer=answer,
                    display_name=stable_bio.display_name,
                    description=stable_bio.description,
                    date_of_birth=stable_bio.date_of_birth,
                    date_of_death=stable_bio.date_of_death,
                    source_kind="stable_bio",
                    source_name="Orac stable biography",
                    confidence="high",
                    search_query=query_text,
                )

        if query.query_type == "cause":
            if fallback_resolution is not None:
                return replace(
                    fallback_resolution,
                    status="needs_generic",
                    failure_message=(
                        "I could not verify a cause of death from Wikidata or Wikipedia."
                    ),
                    needs_generic_retrieval=True,
                )
            return PersonFactResolution(
                status="needs_generic",
                query=query,
                search_query=query_text,
                failure_message=(
                    "I could not verify a cause of death from Wikidata or Wikipedia."
                ),
                needs_generic_retrieval=True,
            )

        if fallback_resolution is not None:
            return fallback_resolution

        return PersonFactResolution(
            status="needs_generic",
            query=query,
            search_query=query_text,
            failure_message=(
                "I could not resolve that person in Wikidata or Wikipedia."
            ),
            needs_generic_retrieval=True,
        )

    def _requires_immediate_disambiguation(
        self,
        resolution: PersonFactResolution,
    ) -> bool:
        """Return whether an ambiguous result should stop source fallback."""
        return (
            resolution.disambiguation_required
            and resolution.identity_confidence == "high"
            and resolution.identity_match_type in {"exact_name", "alias", "context"}
        )

    def _resolve_via_wikidata(
        self,
        query: PersonStatusQuery,
        *,
        today: date,
    ) -> PersonFactResolution | None:
        """Resolve a query from Wikidata search and entity claims."""
        search_results = self._wikidata_search(query.person_name)
        if not search_results:
            self._log_debug(f"Wikidata search returned no results for '{query.person_name}'.")
            return None

        candidates = [
            candidate
            for candidate in (
                self._wikidata_candidate_from_search_item(query, item)
                for item in search_results
            )
            if candidate is not None
        ]
        if not candidates:
            self._log_debug(f"Wikidata search results were not usable for '{query.person_name}'.")
            return None

        selected, ambiguous = self._select_candidate(query, candidates)
        if ambiguous:
            identity = (
                self._identity_match(query, selected)
                if selected is not None
                else None
            )
            clarification = self._clarification_message(selected, query, identity)
            return PersonFactResolution(
                status="ambiguous",
                query=query,
                display_name=selected.display_name,
                description=selected.description,
                clarification=clarification,
                confidence="medium",
                search_query=query.search_query,
                failure_message="Wikidata returned multiple plausible matches.",
                identity_confidence=identity.confidence if identity else "low",
                identity_match_type=identity.match_type if identity else "none",
                requested_name=query.person_name,
                resolved_name=selected.display_name if selected else "",
                aliases_considered=identity.aliases_considered if identity else (),
                disambiguation_required=True,
            )
        if selected is None:
            return None

        return self._resolution_from_candidate(query, selected, today=today)

    def _resolve_via_wikipedia(
        self,
        query: PersonStatusQuery,
        *,
        today: date,
    ) -> PersonFactResolution | None:
        """Resolve a query through Wikipedia search and Wikidata pageprops."""
        search_results = self._wikipedia_search(query.person_name)
        if not search_results:
            self._log_debug(f"Wikipedia search returned no results for '{query.person_name}'.")
            return None

        titles = [
            str(item.get("title", "")).strip()
            for item in search_results
            if isinstance(item, dict) and str(item.get("title", "")).strip()
        ]
        if not titles:
            return None

        candidates: list[_BiographyRecord] = []
        for title in titles:
            summary = self._wikipedia_summary(title)
            if summary is None:
                continue
            wikidata_id = summary.get("wikidata_id")
            display_name = str(summary.get("title") or title).strip()
            description = str(summary.get("description") or "").strip()
            if not wikidata_id:
                candidate = self._candidate_from_wikipedia_summary(query, summary, title)
                if candidate is not None:
                    candidates.append(candidate)
                continue
            entity = self._wikidata_entity(str(wikidata_id))
            if entity is None:
                continue
            candidate = self._candidate_from_wikidata_entity(
                query,
                entity,
                display_name=display_name,
                description=description,
                source_kind="wikipedia",
                source_name="Wikipedia",
                source_url=str(summary.get("url") or ""),
            )
            if candidate is None:
                continue
            candidates.append(candidate)

        if not candidates:
            return None
        selected, ambiguous = self._select_candidate(query, candidates)
        if selected is None:
            return None
        if ambiguous:
            identity = self._identity_match(query, selected)
            return PersonFactResolution(
                status="ambiguous",
                query=query,
                display_name=selected.display_name,
                description=selected.description,
                clarification=self._clarification_message(selected, query, identity),
                confidence="medium",
                search_query=query.search_query,
                failure_message="Wikipedia returned no confirmed identity match.",
                identity_confidence=identity.confidence,
                identity_match_type=identity.match_type,
                requested_name=query.person_name,
                resolved_name=selected.display_name,
                aliases_considered=identity.aliases_considered,
                disambiguation_required=True,
            )
        return self._resolution_from_candidate(query, selected, today=today)

    def _resolution_from_candidate(
        self,
        query: PersonStatusQuery,
        candidate: _BiographyRecord,
        *,
        today: date,
    ) -> PersonFactResolution:
        """Convert a structured candidate into a final resolution."""
        identity = self._identity_match(query, candidate)
        if not identity.allows_direct_answer:
            clarification = self._clarification_message(candidate, query, identity)
            return PersonFactResolution(
                status="ambiguous",
                query=query,
                display_name=candidate.display_name,
                description=candidate.description,
                date_of_birth=candidate.date_of_birth,
                date_of_death=candidate.date_of_death,
                source_kind=candidate.source_kind,
                source_name=candidate.source_name,
                source_url=candidate.source_url,
                confidence="medium",
                search_query=query.search_query,
                clarification=clarification,
                failure_message="Structured lookup did not prove identity.",
                identity_confidence=identity.confidence,
                identity_match_type=identity.match_type,
                requested_name=query.person_name,
                resolved_name=candidate.display_name,
                aliases_considered=identity.aliases_considered,
                disambiguation_required=True,
            )
        if candidate.date_of_death is not None:
            if (
                self._settings.require_corroboration_for_recent_deaths
                and candidate.date_of_death.year > 0
                and self._is_recent_death(candidate.date_of_death, today=today)
                and candidate.source_kind != "stable_bio"
            ):
                return PersonFactResolution(
                    status="needs_generic",
                    query=query,
                    display_name=candidate.display_name,
                    description=candidate.description,
                    date_of_birth=candidate.date_of_birth,
                    date_of_death=candidate.date_of_death,
                    source_kind=candidate.source_kind,
                    source_name=candidate.source_name,
                    source_url=candidate.source_url,
                    confidence="medium",
                    search_query=query.search_query,
                    failure_message=(
                        "I found a likely biography match, but I need broader verification for a recent death."
                    ),
                    needs_generic_retrieval=True,
                    identity_confidence=identity.confidence,
                    identity_match_type=identity.match_type,
                    requested_name=query.person_name,
                    resolved_name=candidate.display_name,
                    aliases_considered=identity.aliases_considered,
                )

        answer = self._build_answer(query, candidate, today=today)
        if answer is None:
            return PersonFactResolution(
                status="needs_generic",
                query=query,
                display_name=candidate.display_name,
                description=candidate.description,
                date_of_birth=candidate.date_of_birth,
                date_of_death=candidate.date_of_death,
                cause_of_death=candidate.cause_of_death,
                source_kind=candidate.source_kind,
                source_name=candidate.source_name,
                source_url=candidate.source_url,
                confidence="medium",
                search_query=query.search_query,
                failure_message=(
                    "I found a likely biography match, but I could not form a reliable answer from it."
                ),
                needs_generic_retrieval=True,
                identity_confidence=identity.confidence,
                identity_match_type=identity.match_type,
                requested_name=query.person_name,
                resolved_name=candidate.display_name,
                aliases_considered=identity.aliases_considered,
            )

        return PersonFactResolution(
            status="resolved",
            query=query,
            answer=answer,
            display_name=candidate.display_name,
            description=candidate.description,
            date_of_birth=candidate.date_of_birth,
            date_of_death=candidate.date_of_death,
            cause_of_death=candidate.cause_of_death,
            source_kind=candidate.source_kind,
            source_name=candidate.source_name,
            source_url=candidate.source_url,
            confidence=candidate.confidence,
            search_query=query.search_query,
            identity_confidence=identity.confidence,
            identity_match_type=identity.match_type,
            requested_name=query.person_name,
            resolved_name=candidate.display_name,
            aliases_considered=identity.aliases_considered,
            disambiguation_required=False,
        )

    def _build_answer(
        self,
        query: PersonStatusQuery,
        candidate: _BiographyRecord,
        *,
        today: date,
    ) -> str | None:
        """Return a natural-language answer for one biography candidate."""
        display_name = self._answer_display_name(query, candidate)
        pronoun = self._subject_pronoun(display_name, candidate.description)

        if query.query_type == "cause":
            if candidate.cause_of_death:
                return f"{display_name}'s cause of death was {candidate.cause_of_death}."
            return None

        if candidate.date_of_birth is None:
            return None

        born_text = format_partial_date(candidate.date_of_birth)
        if candidate.date_of_death is None:
            if query.query_type == "born":
                return f"{display_name} was born on {born_text}."
            if candidate.date_of_birth.is_full:
                age = calculate_age(candidate.date_of_birth.as_date(), today)
                return (
                    f"{display_name} is {age}. "
                    f"{self._birth_sentence_subject(display_name, pronoun)} was born on {born_text}."
                )
            return (
                f"{display_name} was born {born_text}. I do not have enough date precision to calculate a reliable current age."
            )

        died_text = format_partial_date(candidate.date_of_death)
        if query.query_type == "born":
            return f"{display_name} was born on {born_text}."
        if query.query_type in {"death", "status"}:
            return f"{display_name} died on {died_text}."
        if candidate.date_of_birth.is_full and candidate.date_of_death.is_full:
            age_at_death = calculate_age(candidate.date_of_birth.as_date(), candidate.date_of_death.as_date())
            age_today = calculate_age(candidate.date_of_birth.as_date(), today)
            return (
                f"{display_name} was {age_at_death} when "
                f"{self._death_clause_subject(display_name, pronoun)} died. "
                f"{self._birth_sentence_subject(display_name, pronoun)} was born on {born_text} "
                f"and died on {died_text}. "
                f"Had {display_name} still been alive today, "
                f"{self._hypothetical_clause_subject(display_name, pronoun)} would be {age_today}."
            )
        return f"{display_name} was born {born_text} and died on {died_text}."

    def _wikidata_search(self, person_name: str) -> list[dict[str, Any]]:
        """Return Wikidata search results for one person name."""
        params = {
            "action": "wbsearchentities",
            "search": person_name,
            "language": "en",
            "format": "json",
            "limit": "10",
            "type": "item",
        }
        payload = self._fetch_json(f"{_WIKIDATA_API}?{urlencode(params)}")
        if not isinstance(payload, dict):
            return []
        results = payload.get("search")
        if not isinstance(results, list):
            return []
        return [item for item in results if isinstance(item, dict)]

    def _wikipedia_search(self, person_name: str) -> list[dict[str, Any]]:
        """Return Wikipedia search results for one person name."""
        params = {
            "action": "query",
            "list": "search",
            "srsearch": person_name,
            "format": "json",
            "srlimit": "10",
            "utf8": "1",
        }
        payload = self._fetch_json(f"{_WIKIPEDIA_API}?{urlencode(params)}")
        if not isinstance(payload, dict):
            return []
        query = payload.get("query")
        if not isinstance(query, dict):
            return []
        results = query.get("search")
        if not isinstance(results, list):
            return []
        return [item for item in results if isinstance(item, dict)]

    def _wikipedia_summary(self, title: str) -> dict[str, Any] | None:
        """Return a Wikipedia summary record for one title."""
        url = f"{_WIKIPEDIA_SUMMARY}{quote(title.replace(' ', '_'), safe='')}"
        payload = self._fetch_json(url)
        if not isinstance(payload, dict):
            return None
        page_title = str(payload.get("title") or "").strip()
        if not page_title:
            return None
        wikidata_id = None
        if isinstance(payload.get("wikibase_item"), str):
            wikidata_id = str(payload.get("wikibase_item")).strip() or None
        else:
            pageprops = payload.get("pageprops")
            if isinstance(pageprops, dict):
                wikidata_id = str(pageprops.get("wikibase_item") or "").strip() or None
        content_urls = payload.get("content_urls")
        desktop_page = ""
        if isinstance(content_urls, dict):
            desktop = content_urls.get("desktop")
            if isinstance(desktop, dict):
                desktop_page = str(desktop.get("page") or "").strip()
        return {
            "title": page_title,
            "description": str(payload.get("description") or "").strip(),
            "extract": str(payload.get("extract") or "").strip(),
            "url": desktop_page,
            "wikidata_id": wikidata_id,
        }

    def _wikidata_candidate_from_search_item(
        self,
        query: PersonStatusQuery,
        item: dict[str, Any],
    ) -> _BiographyRecord | None:
        """Build a biography candidate from a Wikidata search result."""
        entity_id = str(item.get("id") or "").strip()
        if not entity_id:
            return None
        entity = self._wikidata_entity(entity_id)
        if entity is None:
            return None
        label = str(item.get("label") or "").strip()
        description = str(item.get("description") or "").strip()
        candidate = self._candidate_from_wikidata_entity(
            query,
            entity,
            display_name=label,
            description=description,
            source_kind="wikidata",
            source_name="Wikidata",
            source_url=f"https://www.wikidata.org/wiki/{entity_id}",
        )
        if candidate is not None:
            return candidate
        return None

    def _candidate_from_wikipedia_summary(
        self,
        query: PersonStatusQuery,
        summary: dict[str, Any],
        title: str,
    ) -> _BiographyRecord | None:
        """Build a biography candidate from a Wikipedia summary without Wikidata."""
        extract = str(summary.get("extract") or "")
        if not self._looks_like_person_summary(summary.get("description"), extract):
            return None
        birth = self._summary_partial_date(extract, "born")
        death = self._summary_partial_date(extract, "died")
        if birth is None and death is None:
            return None
        return _BiographyRecord(
            entity_id=title,
            display_name=str(summary.get("title") or title).strip(),
            description=str(summary.get("description") or "").strip(),
            date_of_birth=birth,
            date_of_death=death,
            cause_of_death=None,
            aliases=(),
            wikipedia_title=title,
            source_kind="wikipedia",
            source_name="Wikipedia",
            source_url=str(summary.get("url") or ""),
            confidence="medium",
        )

    def _candidate_from_wikidata_entity(
        self,
        query: PersonStatusQuery,
        entity: dict[str, Any],
        *,
        display_name: str,
        description: str,
        source_kind: str,
        source_name: str,
        source_url: str,
    ) -> _BiographyRecord | None:
        """Build a biography candidate from one Wikidata entity payload."""
        label = str(display_name or entity.get("labels", {}).get("en", {}).get("value") or "").strip()
        entity_description = str(description or entity.get("descriptions", {}).get("en", {}).get("value") or "").strip()
        claims = entity.get("claims")
        if not isinstance(claims, dict):
            return None
        birth = self._claim_date(claims.get("P569"))
        death = self._claim_date(claims.get("P570"))
        cause = self._claim_cause_of_death(claims.get("P509"))
        wikipedia_title = self._wikipedia_title(entity)
        aliases = self._wikidata_aliases(entity)

        if birth is None and death is None and cause is None:
            return None
        if not label:
            label = query.person_name
        if not self._looks_like_person_description(entity_description):
            self._log_debug(
                f"Wikidata entity '{entity.get('id', '')}' did not look like a person."
            )
            return None

        confidence = "high" if birth is not None and (death is not None or query.query_type != "cause") else "medium"
        if self._is_ambiguous_entity(query.person_name, label, entity_description):
            confidence = "medium"
        return _BiographyRecord(
            entity_id=str(entity.get("id") or "").strip() or label,
            display_name=label,
            description=entity_description,
            date_of_birth=birth,
            date_of_death=death,
            cause_of_death=cause,
            aliases=aliases,
            wikipedia_title=wikipedia_title,
            source_kind=source_kind,
            source_name=source_name,
            source_url=source_url,
            confidence=confidence,
        )

    def _select_candidate(
        self,
        query: PersonStatusQuery,
        candidates: list[_BiographyRecord],
    ) -> tuple[_BiographyRecord | None, bool]:
        """Select the best candidate and flag ambiguity when required."""
        if not candidates:
            return None, False
        assessed = [
            (candidate, self._identity_match(query, candidate))
            for candidate in candidates
        ]
        self._log_identity_debug(query, assessed)
        high_matches = [
            (candidate, identity)
            for candidate, identity in assessed
            if identity.allows_direct_answer
        ]
        if len(high_matches) == 1:
            return high_matches[0][0], False
        if len(high_matches) > 1:
            canonical_matches = [
                (candidate, identity)
                for candidate, identity in high_matches
                if self._is_canonical_exact_biography_match(query, candidate, identity)
            ]
            if len(canonical_matches) == 1:
                return canonical_matches[0][0], False
            ranked_high = sorted(
                high_matches,
                key=lambda item: (
                    item[1].score,
                    self._candidate_fact_score(query, item[0]),
                    self._candidate_score(
                        query.person_name,
                        item[0].display_name,
                        item[0].description,
                    ),
                    item[0].confidence,
                ),
                reverse=True,
            )
            return ranked_high[0][0], True

        ranked = sorted(
            assessed,
            key=lambda item: (
                item[1].score,
                self._candidate_score(
                    query.person_name,
                    item[0].display_name,
                    item[0].description,
                ),
                item[0].confidence,
            ),
            reverse=True,
        )
        return ranked[0][0], True

    def _clarification_message(
        self,
        candidate: _BiographyRecord | None,
        query: PersonStatusQuery,
        identity: _IdentityMatch | None = None,
    ) -> str:
        """Return a clarification question for an ambiguous person match."""
        if candidate is None:
            return f"Do you mean {query.person_name}?"
        if (
            identity is not None
            and (
                identity.confidence == "low"
                or identity.match_type in {"none", "weak"}
            )
        ):
            return (
                f"I could not confirm which {query.person_name} you mean. "
                f"Which {query.person_name} do you mean?"
            )
        if identity is not None and identity.confidence == "medium":
            return (
                f"I found a possible match, {candidate.display_name}, but I cannot "
                f"confirm that this is the {query.person_name} you mean. "
                f"Which {query.person_name} do you mean?"
            )
        if candidate.description:
            return f"Do you mean {candidate.display_name}, the {candidate.description}?"
        return f"Do you mean {candidate.display_name}?"

    def _fetch_json(self, url: str) -> Any | None:
        """Fetch and decode a JSON document with conservative error handling."""
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Orac/1.0 (+https://github.com/openai/openai)",
            },
            method="GET",
        )
        try:
            with urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
                raw = response.read()
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            self._log_debug(f"Biography lookup failed for '{url}': {exc}")
            return None
        except Exception as exc:  # pragma: no cover - defensive isolation
            self._log_warning(f"Biography lookup failed for '{url}': {exc}")
            return None
        try:
            return json.loads(raw.decode("utf-8", errors="replace"))
        except Exception as exc:
            self._log_warning(f"Biography lookup returned malformed JSON for '{url}': {exc}")
            return None

    def _wikidata_entity(self, entity_id: str) -> dict[str, Any] | None:
        """Return a Wikidata entity by id."""
        params = {
            "action": "wbgetentities",
            "ids": entity_id,
            "format": "json",
            "props": "labels|aliases|descriptions|claims|sitelinks",
            "languages": "en",
        }
        payload = self._fetch_json(f"{_WIKIDATA_API}?{urlencode(params)}")
        if not isinstance(payload, dict):
            return None
        entities = payload.get("entities")
        if not isinstance(entities, dict):
            return None
        entity = entities.get(entity_id)
        if not isinstance(entity, dict):
            return None
        if entity.get("missing"):
            return None
        return entity

    def _wikidata_aliases(self, entity: dict[str, Any]) -> tuple[str, ...]:
        """Return English aliases from a Wikidata entity."""
        aliases = entity.get("aliases")
        if not isinstance(aliases, dict):
            return ()
        english_aliases = aliases.get("en")
        if not isinstance(english_aliases, list):
            return ()
        values: list[str] = []
        for item in english_aliases:
            if not isinstance(item, dict):
                continue
            value = str(item.get("value") or "").strip()
            if value and value not in values:
                values.append(value)
        return tuple(values)

    def _claim_date(self, claims: Any) -> PartialDate | None:
        """Extract a partial date from a Wikidata date claim list."""
        if not isinstance(claims, list) or not claims:
            return None
        first = claims[0]
        if not isinstance(first, dict):
            return None
        mainsnak = first.get("mainsnak")
        if not isinstance(mainsnak, dict):
            return None
        datavalue = mainsnak.get("datavalue")
        if not isinstance(datavalue, dict):
            return None
        value = datavalue.get("value")
        if not isinstance(value, dict):
            return None
        time_text = str(value.get("time") or "").strip()
        if not time_text:
            return None
        precision = int(value.get("precision") or 0)
        match = re.match(r"^[+-](\d{4,})-(\d{2})-(\d{2})T", time_text)
        if match is None:
            return None
        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3))
        if precision >= 11:
            return PartialDate(year, month, day)
        if precision == 10:
            return PartialDate(year, month, None)
        return PartialDate(year, None, None)

    def _claim_cause_of_death(self, claims: Any) -> str | None:
        """Extract a cause of death label from Wikidata if present."""
        if not isinstance(claims, list) or not claims:
            return None
        first = claims[0]
        if not isinstance(first, dict):
            return None
        mainsnak = first.get("mainsnak")
        if not isinstance(mainsnak, dict):
            return None
        datavalue = mainsnak.get("datavalue")
        if not isinstance(datavalue, dict):
            return None
        value = datavalue.get("value")
        if not isinstance(value, dict):
            return None
        cause_id = str(value.get("id") or "").strip()
        if not cause_id:
            return None
        label = self._wikidata_label(cause_id)
        return label or cause_id

    def _wikidata_label(self, entity_id: str) -> str | None:
        """Return the English label for one Wikidata entity id."""
        params = {
            "action": "wbgetentities",
            "ids": entity_id,
            "format": "json",
            "props": "labels",
            "languages": "en",
        }
        payload = self._fetch_json(f"{_WIKIDATA_API}?{urlencode(params)}")
        if not isinstance(payload, dict):
            return None
        entities = payload.get("entities")
        if not isinstance(entities, dict):
            return None
        entity = entities.get(entity_id)
        if not isinstance(entity, dict):
            return None
        labels = entity.get("labels")
        if not isinstance(labels, dict):
            return None
        label = labels.get("en")
        if not isinstance(label, dict):
            return None
        return str(label.get("value") or "").strip() or None

    def _wikipedia_title(self, entity: dict[str, Any]) -> str | None:
        """Return the associated English Wikipedia title if available."""
        sitelinks = entity.get("sitelinks")
        if not isinstance(sitelinks, dict):
            return None
        enwiki = sitelinks.get("enwiki")
        if not isinstance(enwiki, dict):
            return None
        title = str(enwiki.get("title") or "").strip()
        return title or None

    def _looks_like_person_description(self, description: str) -> bool:
        """Return whether a description looks person-like enough to trust."""
        text = (description or "").strip().lower()
        if not text:
            return False
        return any(hint in text for hint in _PERSON_DESCRIPTION_HINTS)

    def _looks_like_person_summary(self, description: Any, extract: str) -> bool:
        """Return whether a Wikipedia summary appears to describe a person."""
        text = f"{description or ''} {extract or ''}".lower()
        return any(hint in text for hint in _PERSON_DESCRIPTION_HINTS)

    def _summary_partial_date(self, extract: str, verb: str) -> PartialDate | None:
        """Extract a partial date from a Wikipedia summary extract."""
        if not extract:
            return None
        patterns = (
            re.compile(rf"\b{verb}\b[^A-Za-z0-9]+(?P<month>[A-Z][a-z]+)\s+(?P<day>\d{{1,2}}),\s+(?P<year>\d{{4}})", re.I),
            re.compile(rf"\b{verb}\b[^A-Za-z0-9]+(?P<year>\d{{4}})", re.I),
        )
        for pattern in patterns:
            match = pattern.search(extract)
            if match is None:
                continue
            year = int(match.group("year"))
            month_name = match.groupdict().get("month")
            day_text = match.groupdict().get("day")
            if month_name and day_text:
                try:
                    month = datetime.strptime(month_name, "%B").month
                except ValueError:
                    continue
                return PartialDate(year, month, int(day_text))
            return PartialDate(year, None, None)
        return None

    def _is_recent_death(self, death_date: PartialDate, *, today: date) -> bool:
        """Return whether a death date falls within the configured recent window."""
        if not death_date.is_full:
            return True
        try:
            age_days = (today - death_date.as_date()).days
        except ValueError:
            return False
        return age_days <= max(0, int(self._settings.recent_death_days))

    def _subject_pronoun(self, display_name: str, description: str) -> str:
        """Return a stable pronoun for a named person when known or clearly inferable."""
        stable_bio = stable_bio_for_person(display_name)
        if isinstance(stable_bio, PersonBio):
            pronoun = stable_bio.subject_pronoun.strip().lower()
            if pronoun in {"he", "she", "they"}:
                return pronoun
        description_text = f" {description.strip().lower()} "
        if any(
            marker in description_text
            for marker in (
                " male ",
                " actor",
                " businessman",
                " king",
                " prince",
                " sportsman",
                " singer",
                " singer-songwriter",
                " male singer",
            )
        ):
            return "he"
        if any(
            marker in description_text
            for marker in (
                " female ",
                " actress",
                " businesswoman",
                " queen",
                " princess",
                " sportswoman",
                " female singer",
            )
        ):
            return "she"
        return ""

    def _death_clause_subject(self, display_name: str, pronoun: str) -> str:
        """Return a readable subject for a death clause."""
        return pronoun if pronoun in {"he", "she"} else display_name

    def _birth_sentence_subject(self, display_name: str, pronoun: str) -> str:
        """Return a readable subject for a follow-up birth sentence."""
        if pronoun in {"he", "she"}:
            return pronoun.capitalize()
        return display_name

    def _hypothetical_clause_subject(self, display_name: str, pronoun: str) -> str:
        """Return a readable subject for a hypothetical age clause."""
        return pronoun if pronoun in {"he", "she"} else display_name

    def _candidate_score(self, query_name: str, label: str, description: str) -> int:
        """Return a simple ranking score for one biography candidate."""
        simplified_query = self._simplify_name(query_name)
        simplified_label = self._simplify_name(label)
        score = 0
        if simplified_label == simplified_query:
            score += 100
        elif simplified_label.startswith(simplified_query):
            score += 80
        elif simplified_query in simplified_label:
            score += 70
        if description:
            lower_description = description.lower()
            if any(hint in lower_description for hint in _PERSON_DESCRIPTION_HINTS):
                score += 20
        if self._is_ambiguous_entity(query_name, label, description):
            score -= 5
        return score

    def _identity_match(
        self,
        query: PersonStatusQuery,
        candidate: _BiographyRecord,
    ) -> _IdentityMatch:
        """Return whether a candidate identity matches the requested person."""
        requested = query.person_name
        labels = tuple(
            value
            for value in (
                candidate.display_name,
                candidate.wikipedia_title or "",
            )
            if value
        )
        aliases = candidate.aliases
        requested_key = self._normalise_identity_name(requested)

        for label in labels:
            label_key = self._normalise_identity_name(label)
            if label_key and label_key == requested_key:
                return _IdentityMatch(
                    confidence="high",
                    match_type="exact_name",
                    score=100,
                    aliases_considered=aliases,
                    reason=f"requested name matched label/title '{label}'",
                )

        for label in labels:
            if self._is_middle_name_tolerant_match(requested, label):
                return _IdentityMatch(
                    confidence="high",
                    match_type="context",
                    score=85,
                    aliases_considered=aliases,
                    reason=f"requested name matched expanded label/title '{label}'",
                )

        for alias in aliases:
            alias_key = self._normalise_identity_name(alias)
            if alias_key and alias_key == requested_key:
                return _IdentityMatch(
                    confidence="high",
                    match_type="alias",
                    score=95,
                    aliases_considered=aliases,
                    matched_alias=alias,
                    reason=f"requested name matched structured alias '{alias}'",
                )

        for alias in aliases:
            if self._is_middle_name_tolerant_match(requested, alias):
                return _IdentityMatch(
                    confidence="high",
                    match_type="alias",
                    score=90,
                    aliases_considered=aliases,
                    matched_alias=alias,
                    reason=f"requested name matched expanded alias '{alias}'",
                )

        best_overlap = max(
            (
                self._ordered_token_overlap(requested, value)
                for value in (*labels, *aliases)
                if value
            ),
            default=0,
        )
        if best_overlap >= 2:
            return _IdentityMatch(
                confidence="medium",
                match_type="weak",
                score=45,
                aliases_considered=aliases,
                reason="some name tokens overlapped, but not strongly enough",
            )
        return _IdentityMatch(
            confidence="low",
            match_type="none",
            score=0,
            aliases_considered=aliases,
            reason="no reliable identity overlap",
        )

    def _answer_display_name(
        self,
        query: PersonStatusQuery,
        candidate: _BiographyRecord,
    ) -> str:
        """Return the display name to use in a public answer."""
        identity = self._identity_match(query, candidate)
        if (
            identity.match_type == "alias"
            and self._normalise_identity_name(candidate.display_name)
            != self._normalise_identity_name(query.person_name)
        ):
            return f"{candidate.display_name}, born {query.person_name}"
        return candidate.display_name or query.person_name

    def _normalise_identity_name(self, value: str) -> str:
        """Normalise a person name for conservative identity comparison."""
        decomposed = unicodedata.normalize("NFKD", str(value or ""))
        ascii_text = "".join(
            char for char in decomposed if not unicodedata.combining(char)
        )
        ascii_text = ascii_text.lower()
        ascii_text = re.sub(r"\b([a-z])\.", r"\1", ascii_text)
        ascii_text = re.sub(r"[^\w\s'-]+", " ", ascii_text, flags=re.U)
        ascii_text = re.sub(r"[_'-]+", " ", ascii_text)
        return " ".join(ascii_text.split())

    def _identity_tokens(self, value: str) -> list[str]:
        """Return normalised tokens for a person name."""
        return self._normalise_identity_name(value).split()

    def _is_middle_name_tolerant_match(self, requested: str, candidate: str) -> bool:
        """Return whether requested first/last name matches an expanded name."""
        requested_tokens = self._identity_tokens(requested)
        candidate_tokens = self._identity_tokens(candidate)
        if len(requested_tokens) < 2 or len(candidate_tokens) < 2:
            return False
        if requested_tokens == candidate_tokens:
            return True
        if requested_tokens[0] != candidate_tokens[0]:
            return False
        if requested_tokens[-1] != candidate_tokens[-1]:
            return False
        if len(candidate_tokens) <= len(requested_tokens):
            return False
        position = 0
        for token in candidate_tokens:
            if position < len(requested_tokens) and token == requested_tokens[position]:
                position += 1
        return position == len(requested_tokens)

    def _ordered_token_overlap(self, requested: str, candidate: str) -> int:
        """Return count of requested tokens found in candidate in the same order."""
        requested_tokens = self._identity_tokens(requested)
        candidate_tokens = self._identity_tokens(candidate)
        if not requested_tokens or not candidate_tokens:
            return 0
        position = 0
        matches = 0
        for token in candidate_tokens:
            if position < len(requested_tokens) and token == requested_tokens[position]:
                position += 1
                matches += 1
        return matches

    def _log_identity_debug(
        self,
        query: PersonStatusQuery,
        assessed: list[tuple[_BiographyRecord, _IdentityMatch]],
    ) -> None:
        """Log candidate identity checks for retrieval debugging."""
        for candidate, identity in assessed:
            self._log_debug(
                "Person identity candidate: "
                f"requested_name={query.person_name!r} "
                f"candidate_label={candidate.display_name!r} "
                f"aliases={list(identity.aliases_considered)!r} "
                f"identity_confidence={identity.confidence!r} "
                f"identity_match_type={identity.match_type!r} "
                f"score={identity.score} reason={identity.reason!r}"
            )

    def _candidate_fact_score(
        self,
        query: PersonStatusQuery,
        candidate: _BiographyRecord,
    ) -> int:
        """Return how well a candidate supports the requested biography fact."""
        score = 0
        if candidate.date_of_birth is not None:
            score += 10
        if candidate.date_of_death is not None:
            score += 10
        if query.query_type in {"death", "status", "age_at_death"}:
            score += 50 if candidate.date_of_death is not None else 0
        if query.query_type in {"age", "born", "age_at_death"}:
            score += 30 if candidate.date_of_birth is not None else 0
        if query.query_type == "cause":
            score += 50 if candidate.cause_of_death else 0
        return score

    def _is_canonical_exact_biography_match(
        self,
        query: PersonStatusQuery,
        candidate: _BiographyRecord,
        identity: _IdentityMatch,
    ) -> bool:
        """Return whether one exact-name candidate is safe to prefer."""
        if identity.match_type != "exact_name":
            return False
        requested_key = self._normalise_identity_name(query.person_name)
        if self._normalise_identity_name(candidate.display_name) != requested_key:
            return False
        if self._normalise_identity_name(candidate.wikipedia_title or "") != requested_key:
            return False
        if candidate.date_of_birth is None:
            return False
        if query.query_type in {"death", "status", "age", "age_at_death"}:
            return candidate.date_of_death is not None
        return True

    def _description_has_lifespan(self, description: str) -> bool:
        """Return whether a description includes explicit birth/death years."""
        return bool(
            re.search(
                r"\(\s*\d{4}\s*[–-]\s*\d{4}\s*\)",
                str(description or ""),
            )
        )

    def _is_ambiguous_entity(self, query_name: str, label: str, description: str) -> bool:
        """Return whether the candidate appears potentially ambiguous."""
        query_tokens = len(self._simplify_name(query_name).split())
        label_text = self._simplify_name(label)
        if query_tokens <= 1:
            return True
        if "(" in label or ")" in label:
            return True
        if not label_text:
            return True
        return False

    def _simplify_name(self, value: str) -> str:
        """Return a name stripped of punctuation and parenthetical suffixes."""
        cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", str(value or "").strip())
        cleaned = re.sub(r"[^\w\s'-]+", " ", cleaned, flags=re.U)
        return " ".join(cleaned.lower().split())

    def _log_debug(self, message: str) -> None:
        """Log a debug message if a logger is available."""
        log_debug = getattr(self._logger, "log_debug", None)
        if callable(log_debug):
            log_debug(message)

    def _log_warning(self, message: str) -> None:
        """Log a warning message if a logger is available."""
        log_warning = getattr(self._logger, "log_warning", None)
        if callable(log_warning):
            log_warning(message)


def resolve_person_fact(
    query: PersonStatusQuery,
    *,
    settings: RetrievalSettings,
    logger: Any | None = None,
    today: date | None = None,
) -> PersonFactResolution:
    """Resolve a person fact query using preferred biography sources."""
    resolver = PersonFactResolver(settings=settings, logger=logger)
    return resolver.resolve(query, today=today)
