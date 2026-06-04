"""Explicit internet retrieval plumbing for Orac."""
# Author: Clive Bostock
# Date: 2026-05-26
# Description: Provides provider-neutral search, fetch, and grounding helpers.

from .broker import RetrievalSettings
from .broker import SearchBroker
from .decision import RetrievalDecisionService
from .decision import build_topic_signature
from .fetcher import SourceFetcher
from .factual_risk import FactualRiskMatch
from .factual_risk import detect_factual_risk
from .factual_risk import should_force_retrieval
from .factual_support import enforce_high_risk_factual_grounding
from .grounding import GroundingPackBuilder
from .models import FetchedSource
from .models import GroundingPack
from .models import GroundingSource
from .models import RetrievalDecision
from .models import RetrievalOutcome
from .models import RetrievalTurnContext
from .models import SearchRequest
from .models import SearchResult
from .person_status import PartialDate
from .person_status import PersonBio
from .person_status import PersonStatusQuery
from .person_status import answer_from_stable_bio
from .person_status import calculate_age
from .person_status import parse_person_age_or_status_query
from .person_fact_resolver import PersonFactResolution
from .person_fact_resolver import PersonFactResolver
from .person_fact_resolver import resolve_person_fact
from .response_style import build_retrieval_response_guidance
from .response_style import normalize_retrieval_response_style
from .response_style import polish_retrieval_response_text
from .providers import SearXNGSearchProvider
from .providers import SearchProvider
from .service import ExplicitRetrievalService
from .triggers import detect_explicit_search_request

__all__ = [
    "ExplicitRetrievalService",
    "FetchedSource",
    "FactualRiskMatch",
    "GroundingPack",
    "GroundingPackBuilder",
    "GroundingSource",
    "PartialDate",
    "PersonBio",
    "PersonFactResolution",
    "PersonFactResolver",
    "PersonStatusQuery",
    "RetrievalOutcome",
    "RetrievalDecision",
    "RetrievalSettings",
    "RetrievalTurnContext",
    "SearXNGSearchProvider",
    "SearchBroker",
    "RetrievalDecisionService",
    "SearchProvider",
    "SearchRequest",
    "SearchResult",
    "SourceFetcher",
    "answer_from_stable_bio",
    "build_retrieval_response_guidance",
    "build_topic_signature",
    "calculate_age",
    "detect_factual_risk",
    "enforce_high_risk_factual_grounding",
    "detect_explicit_search_request",
    "normalize_retrieval_response_style",
    "parse_person_age_or_status_query",
    "polish_retrieval_response_text",
    "should_force_retrieval",
    "resolve_person_fact",
]
