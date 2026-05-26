"""Explicit internet retrieval plumbing for Orac."""
# Author: Clive Bostock
# Date: 2026-05-26
# Description: Provides provider-neutral search, fetch, and grounding helpers.

from .broker import RetrievalSettings
from .broker import SearchBroker
from .fetcher import SourceFetcher
from .grounding import GroundingPackBuilder
from .models import FetchedSource
from .models import GroundingPack
from .models import GroundingSource
from .models import RetrievalOutcome
from .models import SearchRequest
from .models import SearchResult
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
    "GroundingPack",
    "GroundingPackBuilder",
    "GroundingSource",
    "RetrievalOutcome",
    "RetrievalSettings",
    "SearXNGSearchProvider",
    "SearchBroker",
    "SearchProvider",
    "SearchRequest",
    "SearchResult",
    "SourceFetcher",
    "build_retrieval_response_guidance",
    "detect_explicit_search_request",
    "normalize_retrieval_response_style",
    "polish_retrieval_response_text",
]
