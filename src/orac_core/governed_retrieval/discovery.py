"""Authorised semantic knowledge-domain discovery for governed retrieval."""

# Author: Clive Bostock
# Date: 2026-08-29
# Description: Builds bounded invocation-scoped domain offers from authorised metadata.

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field, replace
import hashlib
import math
import re
import secrets
import threading
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping

from model.plugin_routing.embeddings import EmbeddingProvider
from orac_core.conversation_memory.models import RetrievalDomain
from orac_core.conversation_memory.models import LogicalRetrievalRequest
from orac_core.conversation_memory.models import TrustedRetrievalContext
from orac_core.embedding_providers import OllamaEmbeddingProvider
from orac_core.knowledge.repository import default_orac_session
from orac_core.knowledge.scope import KnowledgeScope

_TERM = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", re.IGNORECASE)
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "for",
        "how",
        "i",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "what",
        "with",
        "would",
    }
)


@dataclass(frozen=True, slots=True)
class AuthorisedKnowledgeDomain:
    """One host-only authorised catalogue entry before semantic ranking."""

    domain_type: RetrievalDomain
    stable_identity: str
    display_name: str
    description: str
    descriptor_version: str
    scope: KnowledgeScope | None = None
    aliases: tuple[str, ...] = ()
    plugin_bridge: Any | None = None

    @property
    def descriptor_text(self) -> str:
        """Render only safe governed metadata into a semantic descriptor."""
        parts = [f"Name: {self.display_name}"]
        if self.description:
            parts.append(f"Description: {self.description}")
        if self.aliases:
            parts.append("Aliases/topics: " + ", ".join(self.aliases))
        return "\n".join(parts)


@dataclass(frozen=True, slots=True)
class KnowledgeDomainAdvertisement:
    """Safe model-facing metadata for one invocation-scoped domain."""

    handle: str
    domain_type: RetrievalDomain
    display_name: str
    description: str
    relevance_score: float | None


@dataclass(frozen=True, slots=True)
class AuthorisedDomainBinding:
    """Host-only mapping from an opaque handle to exact retrieval authority."""

    advertisement: KnowledgeDomainAdvertisement
    stable_identity: str
    advertised_order: int
    domain_weight: float
    scope: KnowledgeScope | None = None
    plugin_bridge: Any | None = None


@dataclass(frozen=True, slots=True)
class DomainDiscoveryTelemetry:
    """Content-free per-turn discovery measurements suitable for audit."""

    authorised_catalogue_size: int = 0
    domains_scored: int = 0
    semantic_matches: int = 0
    semantic_advertised_count: int = 0
    conversation_advertised_count: int = 0
    advertised_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    embedding_batches: int = 0
    conversation_available: bool = False
    fallback_mode: str = "NONE"
    duration_ms: int = 0
    profile_identity: str = ""


@dataclass(frozen=True, slots=True)
class KnowledgeDomainOffer:
    """One immutable invocation offer and its trusted handle bindings."""

    advertisements: tuple[KnowledgeDomainAdvertisement, ...]
    bindings: Mapping[str, AuthorisedDomainBinding]
    telemetry: DomainDiscoveryTelemetry = field(
        default_factory=DomainDiscoveryTelemetry
    )

    def __post_init__(self) -> None:
        """Freeze and validate the exact advertisement-to-binding authority map."""
        handles = tuple(item.handle for item in self.advertisements)
        if len(set(handles)) != len(handles):
            raise ValueError("domain offer contains duplicate handles")
        bindings = dict(self.bindings)
        if set(bindings) != set(handles):
            raise ValueError("domain offer bindings do not match advertisements")
        if any(
            bindings[handle].advertisement != advertisement
            for handle, advertisement in zip(handles, self.advertisements, strict=True)
        ):
            raise ValueError("domain offer binding metadata is inconsistent")
        object.__setattr__(self, "bindings", MappingProxyType(bindings))

    def binding(self, handle: str) -> AuthorisedDomainBinding | None:
        """Return an exact current-invocation binding without string fallback."""
        return self.bindings.get(handle)

    def render_instruction(self) -> str:
        """Render the bounded safe catalogue for the primary model invocation."""
        lines = [
            "Available governed knowledge domains for this invocation:",
            "Select only the exact opaque handles below when calling retrieve.",
        ]
        if self.telemetry.semantic_matches > 0:
            lines.extend(
                [
                    "At least one governed domain semantically matches the current "
                    "question.",
                    "The catalogue text is routing metadata, not answer evidence. "
                    "You MUST call retrieve exactly once before answering.",
                ]
            )
        for item in self.advertisements:
            lines.append(
                f"{item.handle} - {item.display_name} [{item.domain_type.value}]"
            )
            lines.append(item.description)
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class FederatedRetrievalRequest:
    """One validated query over a bounded list of advertised handles."""

    query: str
    domain_handles: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate the scope-free model request after schema validation."""
        query = str(self.query or "").strip()
        if not query or len(query) > 2048:
            raise ValueError("federated retrieval query is invalid")
        if not self.domain_handles:
            raise ValueError("at least one domain handle is required")
        if len(set(self.domain_handles)) != len(self.domain_handles):
            raise ValueError("domain handles must be unique")
        object.__setattr__(self, "query", query)


@dataclass(frozen=True, slots=True)
class FederatedEvidenceCandidate:
    """One domain-tagged candidate retaining its native rank and score."""

    domain_handle: str
    domain_type: RetrievalDomain
    advertised_order: int
    domain_weight: float
    within_domain_rank: int
    native_score: float | None
    source_identity: str
    evidence: Any


@dataclass(frozen=True, slots=True)
class FederatedGovernedRetrievalResult:
    """Merged result from independently authorised governed adapters."""

    status: str
    reason_codes: tuple[str, ...]
    evidence: tuple[FederatedEvidenceCandidate, ...] = ()
    provenance: Mapping[str, Any] | None = None
    selected_handles: tuple[str, ...] = ()
    successful_domain_types: tuple[str, ...] = ()
    unavailable_count: int = 0


def federated_rank_candidates(
    candidates_by_binding: tuple[tuple[AuthorisedDomainBinding, tuple[Any, ...]], ...],
    *,
    maximum_items: int,
) -> tuple[FederatedEvidenceCandidate, ...]:
    """Merge native ranks using domain weights, diversity, and weighted RRF."""
    if maximum_items <= 0:
        return ()
    wrapped: list[FederatedEvidenceCandidate] = []
    for binding, evidence_items in candidates_by_binding:
        for rank, evidence in enumerate(evidence_items, start=1):
            wrapped.append(
                FederatedEvidenceCandidate(
                    domain_handle=binding.advertisement.handle,
                    domain_type=binding.advertisement.domain_type,
                    advertised_order=binding.advertised_order,
                    domain_weight=binding.domain_weight,
                    within_domain_rank=rank,
                    native_score=_native_score(evidence),
                    source_identity=_source_identity(
                        binding.advertisement.domain_type, evidence, rank
                    ),
                    evidence=evidence,
                )
            )

    first_by_handle = {
        item.domain_handle: item for item in wrapped if item.within_domain_rank == 1
    }
    seed = sorted(
        first_by_handle.values(),
        key=lambda item: (
            -item.domain_weight,
            item.advertised_order,
            item.source_identity,
        ),
    )
    seeded_ids = {(item.domain_handle, item.within_domain_rank) for item in seed}
    remaining = sorted(
        (
            item
            for item in wrapped
            if (item.domain_handle, item.within_domain_rank) not in seeded_ids
        ),
        key=lambda item: (
            -(item.domain_weight / (60.0 + item.within_domain_rank)),
            -item.domain_weight,
            item.advertised_order,
            item.within_domain_rank,
            item.source_identity,
        ),
    )
    return tuple((seed + remaining)[:maximum_items])


class FederatedRetrievalExecutor:
    """Execute advertised bindings through existing independently governed adapters."""

    def __init__(
        self,
        *,
        mediator: Any,
        project_authorizer: Any | None,
        max_evidence_items: int,
    ) -> None:
        """Initialise with existing mediation and authority boundaries."""
        self._mediator = mediator
        self._project_authorizer = project_authorizer
        self._max_evidence_items = max(1, max_evidence_items)

    def retrieve(
        self,
        request: FederatedRetrievalRequest,
        *,
        offer: KnowledgeDomainOffer,
        context: TrustedRetrievalContext,
    ) -> FederatedGovernedRetrievalResult:
        """Reauthorise and retrieve each formerly advertised binding independently."""
        successful: list[tuple[AuthorisedDomainBinding, tuple[Any, ...]]] = []
        provenance_by_handle: dict[str, Any] = {}
        successful_types: list[str] = []
        unavailable_count = 0
        for handle in request.domain_handles:
            binding = offer.binding(handle)
            if binding is None:
                return FederatedGovernedRetrievalResult(
                    status="failed",
                    reason_codes=("invalid_domain_selection",),
                    selected_handles=request.domain_handles,
                )
            bound_context = replace(
                context,
                project_scope=binding.scope,
                plugin_retrieval_bridge=binding.plugin_bridge,
            )
            try:
                binding_current = self._binding_is_current(
                    binding, context=bound_context
                )
            except Exception:
                binding_current = False
            if not binding_current:
                unavailable_count += 1
                provenance_by_handle[handle] = {
                    "domain_type": binding.advertisement.domain_type.value,
                    "status": "unavailable",
                }
                continue
            try:
                governed = self._mediator.retrieve(
                    LogicalRetrievalRequest(
                        query=request.query,
                        domain=binding.advertisement.domain_type,
                    ),
                    context=bound_context,
                )
            except Exception:
                unavailable_count += 1
                provenance_by_handle[handle] = {
                    "domain_type": binding.advertisement.domain_type.value,
                    "status": "unavailable",
                }
                continue
            if governed.status == "failed":
                unavailable_count += 1
                provenance_by_handle[handle] = {
                    "domain_type": binding.advertisement.domain_type.value,
                    "status": "unavailable",
                }
                continue
            successful.append((binding, tuple(governed.evidence)))
            successful_types.append(binding.advertisement.domain_type.value)
            source_provenance = dict(governed.provenance or {})
            source_provenance.pop("scope_key", None)
            provenance_by_handle[handle] = {
                "domain_type": binding.advertisement.domain_type.value,
                "domain_display_name": binding.advertisement.display_name,
                "status": governed.status,
                "source": source_provenance,
                "candidate_count": len(governed.evidence),
            }

        evidence = federated_rank_candidates(
            tuple(successful),
            maximum_items=self._max_evidence_items,
        )
        if evidence:
            status = "grounded"
            reasons: tuple[str, ...] = ("federated_evidence_selected",)
            if unavailable_count:
                reasons += ("domain_unavailable",)
        elif successful:
            status = "no_evidence"
            reasons = ("no_relevant_evidence",)
        else:
            status = "unavailable" if unavailable_count else "no_evidence"
            reasons = (
                ("retrieval_unavailable",)
                if unavailable_count
                else ("no_relevant_evidence",)
            )
        return FederatedGovernedRetrievalResult(
            status=status,
            reason_codes=reasons,
            evidence=evidence,
            provenance={"domains": provenance_by_handle},
            selected_handles=request.domain_handles,
            successful_domain_types=tuple(successful_types),
            unavailable_count=unavailable_count,
        )

    def _binding_is_current(
        self,
        binding: AuthorisedDomainBinding,
        *,
        context: TrustedRetrievalContext,
    ) -> bool:
        """Revalidate exact authority immediately before one adapter invocation."""
        domain = binding.advertisement.domain_type
        if domain is RetrievalDomain.PROJECT:
            if binding.scope is None or self._project_authorizer is None:
                return False
            resolution = self._project_authorizer.resolve_for_user(
                context.principal_username,
                (binding.scope.canonical_name,),
            )
            return resolution.status == "authorised" and resolution.scopes == (
                binding.scope,
            )
        if domain is RetrievalDomain.CONVERSATION:
            return RetrievalDomain.CONVERSATION in self._mediator.available_domains(
                context=context
            )
        if domain is RetrievalDomain.PLUGIN:
            return binding.plugin_bridge is not None
        return False


def _native_score(evidence: Any) -> float | None:
    """Read a native score for audit without comparing it across domains."""
    for name in ("relevance_score", "score", "lexical_score", "semantic_score"):
        value = getattr(evidence, name, None)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


def _source_identity(
    domain_type: RetrievalDomain,
    evidence: Any,
    rank: int,
) -> str:
    """Build a deterministic content-free tie-break identity."""
    values = [domain_type.value]
    for name in (
        "conversation_id",
        "checkpoint_id",
        "message_id",
        "document_id",
        "document_version_id",
        "chunk_id",
        "chunk_no",
    ):
        value = getattr(evidence, name, None)
        if value is not None:
            values.append(f"{name}:{value}")
    if len(values) == 1:
        values.append(f"rank:{rank}")
    return "|".join(values)


class AuthorisedKnowledgeDomainRepository:
    """Read current authorised catalogue facts through ORAC_CODE packages."""

    _AUTH_PACKAGE = "orac_code.rag_usage_authorization_api"
    _MEMORY_PACKAGE = "orac_code.conversation_memory_api"

    def __init__(self, *, session_factory: Callable[[], Any] | None = None) -> None:
        """Initialise with an injectable runtime session factory."""
        self._session_factory = session_factory or default_orac_session

    def load_authorised_projects(
        self,
        principal_username: str,
        candidate_limit: int,
    ) -> list[dict[str, Any]]:
        """Return the complete current authorised PROJECT descriptor catalogue."""
        return self._call_cursor(
            f"{self._AUTH_PACKAGE}.open_authorised_project_domains",
            [principal_username, candidate_limit],
        )

    def has_retrievable_conversation_memory(
        self,
        principal_username: str,
        embedding_model: str,
        embedding_dimensions: int,
    ) -> bool:
        """Return content-free principal memory availability."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                value = cursor.callfunc(
                    f"{self._MEMORY_PACKAGE}.has_retrievable_memory",
                    str,
                    [principal_username, embedding_model, embedding_dimensions],
                )
            return str(value or "N").upper() == "Y"
        finally:
            _close_quietly(session)

    def _call_cursor(self, name: str, inputs: list[Any]) -> list[dict[str, Any]]:
        """Materialise a package cursor before closing its session."""
        session = self._session_factory()
        try:
            with session.cursor() as cursor:
                result_cursor = session.cursor()
                try:
                    cursor.callproc(name, [*inputs, result_cursor])
                    columns = [item[0].lower() for item in result_cursor.description]
                    return [
                        dict(zip(columns, values, strict=True))
                        for values in result_cursor.fetchall()
                    ]
                finally:
                    result_cursor.close()
        finally:
            _close_quietly(session)


class DomainDiscoveryService:
    """Rank authorised domain descriptors and issue a bounded opaque offer."""

    def __init__(
        self,
        *,
        repository: Any,
        embedding_provider: EmbeddingProvider,
        profile_identity: str,
        descriptor_schema_version: str,
        aliases: Mapping[str, KnowledgeScope] | None = None,
        minimum_score: float = 0.50,
        semantic_weight: float = 0.85,
        lexical_weight: float = 0.15,
        embedding_batch_size: int = 64,
        catalogue_hard_limit: int = 4096,
        max_advertised_domains: int = 3,
        max_catalogue_characters: int = 2000,
        cache_max_entries: int = 8192,
        conversation_embedding_model: str = "",
        conversation_embedding_dimensions: int = 0,
        project_discovery_enabled: bool = True,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialise bounded ranking and descriptor-vector caching."""
        if not 0.0 <= minimum_score <= 1.0:
            raise ValueError("domain minimum score must be between 0 and 1")
        if semantic_weight < 0 or lexical_weight < 0:
            raise ValueError("domain discovery weights must not be negative")
        if not math.isclose(semantic_weight + lexical_weight, 1.0, abs_tol=1e-9):
            raise ValueError("domain discovery weights must sum to 1")
        for name, value in (
            ("embedding_batch_size", embedding_batch_size),
            ("catalogue_hard_limit", catalogue_hard_limit),
            ("max_advertised_domains", max_advertised_domains),
            ("max_catalogue_characters", max_catalogue_characters),
            ("cache_max_entries", cache_max_entries),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        self._repository = repository
        self._embedding_provider = embedding_provider
        self._profile_identity = str(profile_identity).strip()
        self._descriptor_schema_version = str(descriptor_schema_version).strip()
        self._minimum_score = minimum_score
        self._semantic_weight = semantic_weight
        self._lexical_weight = lexical_weight
        self._embedding_batch_size = embedding_batch_size
        self._catalogue_hard_limit = catalogue_hard_limit
        self._max_advertised_domains = max_advertised_domains
        self._max_catalogue_characters = max_catalogue_characters
        self._cache_max_entries = cache_max_entries
        self._clock = clock
        self._cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()
        self._cache_lock = threading.RLock()
        self._aliases = dict(aliases or {})
        self._conversation_embedding_model = str(
            conversation_embedding_model or ""
        ).strip()
        self._conversation_embedding_dimensions = int(conversation_embedding_dimensions)
        self._project_discovery_enabled = bool(project_discovery_enabled)

    def discover(
        self,
        *,
        query: str,
        principal_username: str,
        conversation_eligible: bool,
        plugin_domain: AuthorisedKnowledgeDomain | None = None,
        include_projects: bool = True,
    ) -> KnowledgeDomainOffer:
        """Build an invocation offer from only currently authorised domains."""
        started = self._clock()
        discovery_query = str(query or "").strip()[:4096]
        rows = (
            self._repository.load_authorised_projects(
                principal_username,
                self._catalogue_hard_limit + 1,
            )
            if self._project_discovery_enabled and include_projects
            else []
        )
        catalogue_size = (
            int(rows[0].get("authorised_catalogue_size") or len(rows)) if rows else 0
        )
        conversation_available = False
        if (
            conversation_eligible
            and self._conversation_embedding_model
            and self._conversation_embedding_dimensions > 0
        ):
            conversation_available = bool(
                self._repository.has_retrievable_conversation_memory(
                    principal_username,
                    self._conversation_embedding_model,
                    self._conversation_embedding_dimensions,
                )
            )

        fallback_mode = "NONE"
        semantic_domains: list[AuthorisedKnowledgeDomain] = []
        if include_projects and not self._project_discovery_enabled:
            fallback_mode = "PROJECT_AUTHORITY_UNAVAILABLE"
        elif catalogue_size > self._catalogue_hard_limit:
            fallback_mode = "CATALOGUE_HARD_LIMIT"
        elif include_projects:
            semantic_domains.extend(self._project_domain(row) for row in rows)
        if plugin_domain is not None:
            semantic_domains.append(
                replace(
                    plugin_domain,
                    display_name=plugin_domain.display_name[:200],
                    description=plugin_domain.description[:500],
                    aliases=tuple(alias[:100] for alias in plugin_domain.aliases[:20]),
                )
            )

        scored_count = 0
        try:
            ranked, cache_hits, cache_misses, batches = self._rank_semantic_domains(
                discovery_query,
                tuple(semantic_domains),
            )
            scored_count = len(semantic_domains) if discovery_query else 0
        except Exception:
            ranked = []
            cache_hits = 0
            cache_misses = 0
            batches = 0
            fallback_mode = "SEMANTIC_PROVIDER_UNAVAILABLE"

        ranked.sort(
            key=lambda pair: (
                -pair[0],
                pair[1].domain_type.value,
                pair[1].display_name.casefold(),
                pair[1].stable_identity,
            )
        )
        slots = self._max_advertised_domains - (1 if conversation_available else 0)
        selected = ranked[: max(0, slots)]
        advertisements: list[KnowledgeDomainAdvertisement] = []
        bindings: dict[str, AuthorisedDomainBinding] = {}

        if conversation_available:
            self._append_offer_entry(
                advertisements,
                bindings,
                domain=AuthorisedKnowledgeDomain(
                    domain_type=RetrievalDomain.CONVERSATION,
                    stable_identity="principal-conversation-memory",
                    display_name="Previous conversations",
                    description=(
                        "Prior discussions and decisions available for governed recall."
                    ),
                    descriptor_version="availability-v1",
                ),
                relevance_score=None,
                domain_weight=0.875,
            )
        for score, domain in selected:
            normalised = (
                (score - self._minimum_score) / (1.0 - self._minimum_score)
                if self._minimum_score < 1.0
                else 1.0
            )
            self._append_offer_entry(
                advertisements,
                bindings,
                domain=domain,
                relevance_score=score,
                domain_weight=0.75 + 0.25 * min(1.0, max(0.0, normalised)),
            )

        while (
            advertisements
            and len(
                KnowledgeDomainOffer(
                    tuple(advertisements), bindings
                ).render_instruction()
            )
            > self._max_catalogue_characters
        ):
            removed = advertisements.pop()
            bindings.pop(removed.handle, None)

        telemetry = DomainDiscoveryTelemetry(
            authorised_catalogue_size=catalogue_size,
            domains_scored=scored_count,
            semantic_matches=len(ranked),
            semantic_advertised_count=sum(
                item.domain_type is not RetrievalDomain.CONVERSATION
                for item in advertisements
            ),
            conversation_advertised_count=sum(
                item.domain_type is RetrievalDomain.CONVERSATION
                for item in advertisements
            ),
            advertised_count=len(advertisements),
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            embedding_batches=batches,
            conversation_available=conversation_available,
            fallback_mode=fallback_mode,
            duration_ms=max(0, int((self._clock() - started) * 1000)),
            profile_identity=self._profile_identity,
        )
        return KnowledgeDomainOffer(tuple(advertisements), bindings, telemetry)

    def _rank_semantic_domains(
        self,
        query: str,
        domains: tuple[AuthorisedKnowledgeDomain, ...],
    ) -> tuple[
        list[tuple[float, AuthorisedKnowledgeDomain]],
        int,
        int,
        int,
    ]:
        """Embed and rank a bounded descriptor set, reusing cached vectors."""
        if not domains or not query:
            return [], 0, 0, 0
        query_vector = tuple(self._embedding_provider.embed_text(query))
        keys = [self._cache_key(item) for item in domains]
        missing: list[tuple[str, AuthorisedKnowledgeDomain]] = []
        vectors_by_key: dict[str, tuple[float, ...]] = {}
        cache_hits = 0
        cache_misses = 0
        batches = 0
        with self._cache_lock:
            for key, item in zip(keys, domains, strict=True):
                if key in self._cache:
                    cache_hits += 1
                    self._cache.move_to_end(key)
                    vectors_by_key[key] = self._cache[key]
                else:
                    cache_misses += 1
                    missing.append((key, item))
        for offset in range(0, len(missing), self._embedding_batch_size):
            batch = missing[offset : offset + self._embedding_batch_size]
            vectors = self._embedding_provider.embed_texts(
                [item.descriptor_text for _, item in batch]
            )
            if len(vectors) != len(batch):
                raise ValueError("descriptor embedding response count is invalid")
            batches += 1
            validated_vectors = [
                tuple(float(value) for value in vector) for vector in vectors
            ]
            vectors_by_key.update(
                (key, vector)
                for (key, _), vector in zip(batch, validated_vectors, strict=True)
            )
            with self._cache_lock:
                for (key, _), vector in zip(batch, validated_vectors, strict=True):
                    self._cache[key] = vector
                    self._cache.move_to_end(key)
                    while len(self._cache) > self._cache_max_entries:
                        self._cache.popitem(last=False)
        ranked: list[tuple[float, AuthorisedKnowledgeDomain]] = []
        for item, key in zip(domains, keys, strict=True):
            semantic = max(0.0, _cosine(query_vector, vectors_by_key[key]))
            lexical = _lexical_coverage(query, item.descriptor_text)
            score = self._semantic_weight * semantic + self._lexical_weight * lexical
            if score >= self._minimum_score:
                ranked.append((score, item))
        return ranked, cache_hits, cache_misses, batches

    def _project_domain(self, row: Mapping[str, Any]) -> AuthorisedKnowledgeDomain:
        """Convert one authorised database row into host-only descriptor state."""
        project_code = str(row.get("project_code") or "").strip()
        scope = KnowledgeScope("PROJECT", project_code)
        aliases = tuple(
            alias[:100]
            for alias in sorted(
                alias for alias, target in self._aliases.items() if target == scope
            )[:20]
        )
        return AuthorisedKnowledgeDomain(
            domain_type=RetrievalDomain.PROJECT,
            stable_identity=f"PROJECT:{project_code}",
            display_name=str(row.get("display_name") or project_code).strip(),
            description=str(row.get("description") or "").strip()[:500],
            descriptor_version=str(row.get("descriptor_version") or "0"),
            scope=scope,
            aliases=aliases,
        )

    def _cache_key(self, domain: AuthorisedKnowledgeDomain) -> str:
        """Return a cache key invalidated by profile, schema, row, or text changes."""
        digest = hashlib.sha256(domain.descriptor_text.encode("utf-8")).hexdigest()
        return "|".join(
            (
                self._profile_identity,
                self._embedding_provider.model_id,
                self._descriptor_schema_version,
                domain.domain_type.value,
                domain.stable_identity,
                domain.descriptor_version,
                digest,
            )
        )

    @staticmethod
    def _append_offer_entry(
        advertisements: list[KnowledgeDomainAdvertisement],
        bindings: dict[str, AuthorisedDomainBinding],
        *,
        domain: AuthorisedKnowledgeDomain,
        relevance_score: float | None,
        domain_weight: float,
    ) -> None:
        """Issue one random handle and retain its exact trusted mapping."""
        handle = "d_" + secrets.token_urlsafe(12)
        advertisement = KnowledgeDomainAdvertisement(
            handle=handle,
            domain_type=domain.domain_type,
            display_name=domain.display_name,
            description=domain.description,
            relevance_score=relevance_score,
        )
        order = len(advertisements)
        advertisements.append(advertisement)
        bindings[handle] = AuthorisedDomainBinding(
            advertisement=advertisement,
            stable_identity=domain.stable_identity,
            advertised_order=order,
            domain_weight=domain_weight,
            scope=domain.scope,
            plugin_bridge=domain.plugin_bridge,
        )


def domain_discovery_embedding_provider(
    config_mgr: Any,
) -> tuple[EmbeddingProvider, str]:
    """Build the dedicated logical domain-discovery embedding profile."""
    section = "embedding.domain_discovery"
    provider_code = (
        str(config_mgr.config_value(section, "provider", default="ollama"))
        .strip()
        .lower()
    )
    if provider_code != "ollama":
        raise ValueError(
            f"unsupported domain discovery embedding provider '{provider_code}'"
        )
    service_url = str(
        config_mgr.config_value(section, "service_url", default="")
    ).strip()
    model_id = str(config_mgr.config_value(section, "model_id", default="")).strip()
    dimensions = config_mgr.int_config_value(section, "dimensions", default=0)
    profile_version = str(
        config_mgr.config_value(section, "profile_version", default="")
    ).strip()
    if not profile_version:
        raise ValueError("domain discovery profile_version is required")
    provider = OllamaEmbeddingProvider(
        service_url=service_url,
        model_id=model_id,
        dimensions=dimensions,
    )
    identity = f"{provider_code}:{model_id}:{dimensions}:{profile_version}"
    return provider, identity


def _cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    """Return deterministic cosine similarity for same-sized finite vectors."""
    if not left or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _lexical_coverage(query: str, descriptor: str) -> float:
    """Return query-term coverage as a bounded secondary discovery signal."""
    query_terms = {
        token.casefold()
        for token in _TERM.findall(query)
        if token.casefold() not in _STOP_WORDS
    }
    if not query_terms:
        return 0.0
    descriptor_terms = {token.casefold() for token in _TERM.findall(descriptor)}
    return len(query_terms & descriptor_terms) / len(query_terms)


def _close_quietly(session: Any) -> None:
    """Close a runtime session without masking the primary result."""
    try:
        session.close()
    except Exception:
        pass
