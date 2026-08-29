"""Governed provenance-backed conversational memory."""

# Author: Clive Bostock
# Date: 2026-08-28
# Description: Exports conversation retention, materialisation, and retrieval APIs.

from .mediation import HostRetrievalMediator
from .embeddings import OllamaConversationEmbeddingProvider
from .embeddings import conversation_embedding_provider
from .models import ConversationMemoryEvidence
from .models import ConversationMemoryGroundingPack
from .models import ConversationMemoryProvenance
from .models import ConversationMemoryRetrievalOutcome
from .models import GovernedRetrievalResult
from .models import LogicalRetrievalRequest
from .models import RetrievalDomain
from .models import RetrievalInitiator
from .models import TrustedRetrievalContext
from .policy import MemoryIntentDecision
from .policy import MemoryIntentPolicy
from .repository import ConversationMemoryRepository
from .retrieval import ConversationMemoryGroundingPackBuilder
from .retrieval import ConversationMemoryRetrievalError
from .retrieval import ConversationMemoryRetrievalService
from .worker import ConversationMemoryMaterialisationService
from .worker import DeterministicConversationSummariser

__all__ = [
    "ConversationMemoryEvidence",
    "ConversationMemoryGroundingPack",
    "ConversationMemoryGroundingPackBuilder",
    "ConversationMemoryProvenance",
    "ConversationMemoryRetrievalError",
    "ConversationMemoryRetrievalOutcome",
    "ConversationMemoryRetrievalService",
    "ConversationMemoryMaterialisationService",
    "ConversationMemoryRepository",
    "DeterministicConversationSummariser",
    "GovernedRetrievalResult",
    "HostRetrievalMediator",
    "LogicalRetrievalRequest",
    "MemoryIntentDecision",
    "MemoryIntentPolicy",
    "OllamaConversationEmbeddingProvider",
    "RetrievalDomain",
    "RetrievalInitiator",
    "TrustedRetrievalContext",
    "conversation_embedding_provider",
]
