# Governed Semantic Retrieval

Phase 2A gives eligible local model runtimes one read-only `retrieve` tool over
logical `CONVERSATION`, `PROJECT`, and `PLUGIN` domains. Orac remains the
security boundary. A model can provide only the retrieval query and one domain
from the exact schema advertised for that turn.

## Authority

The host derives the authenticated principal and every concrete scope.
Conversation retrieval enforces principal ownership. PROJECT retrieval reuses
the existing Oracle RAG USE authorization for the configured project scope.
PLUGIN retrieval is advertised only when a trusted plugin identity and
self-scope entitlement are already bound to the runtime request. A request
cannot nominate a username, user ID, project ID, plugin ID, conversation ID,
checkpoint ID, or database selector.

The shared host mediator federates these independently governed services; it
does not replace their authorization contracts or storage.

## Eligibility and Runtime Health

Effective mode resolution is capability based:

1. Without verified `structured_tool_calling` evidence, the mode is `NONE`.
2. With structured evidence but without verified streamed evidence, the mode
   is `BUFFERED`.
3. With bounded-probe-verified streamed capability evidence and compatible
   provider framing, the mode is
   `STREAMING` while operational streaming health remains acceptable.
4. Temporary framing-health suppression selects `BUFFERED` without changing
   authoritative model capability evidence.

Capability definitions are installed by Liquibase. Exact model evidence
remains an explicit administrative record; runtime telemetry never creates,
rewrites, or revokes it and no model-name allowlist is used.

The bounded host probe uses only a fixed fixture query, never executes the
requested retrieval, and reports framing validity, completion, malformed or
incomplete calls, time from first visible output to tool start, and visible
characters before tool start. Its report is review input; it does not mutate
capability evidence automatically.

Run the fixed probe against the configured local provider and model with:

```bash
.venv/bin/python scripts/probe_governed_retrieval.py --pretty
```

A successful report is necessary review input, not an authorization to insert
evidence by itself.

## Streaming Semantics

In `STREAMING` mode, a bounded commit gate briefly retains visible assistant
text. An early valid call discards that buffered text, performs one governed
retrieval, and streams a tools-disabled final continuation. A direct answer is
committed when either configured character or delay threshold is reached and
then continues through the ordinary streaming path.

Once visible text is committed, retrieval authority closes for the turn. A
late call is ignored and ordinary provider text continues. Orac makes one
tools-disabled suffix continuation only when provider framing terminates the
direct answer at that rejected late call. The committed prefix is preserved
and only the suffix is streamed.

Raw tool frames, arguments, evidence payloads, reasoning, discarded assistant
text, and validation failures never enter client text or TTS output.

## Context and Persistence

Orac accounts for the base prompt, serialized schema, provider framing,
response allowance, safety reserve, and independently bounded evidence. A
final check runs after tool-result serialization. Unsafe evidence is not added
to the provider transcript.

Assistant tool-call and tool-result messages exist only in the ephemeral
provider transcript. Orac persists the real user message, the authoritative
final assistant answer, and safe provenance. Retrieval is read-only: models
cannot delete or mutate memory, promote statements into facts, or change
authorization scope.

## Audit and Operations

The append-only retrieval audit stores allowlisted metadata such as effective
mode, early/late timing, whether visible content was already committed,
temporary health state, continuation recovery, and final invocation
correlation. It does not store queries, arguments, evidence, prompts,
reasoning, or discarded text.

Monitor commit delay, characters before commitment, early and late calls,
malformed or incomplete calls, recovery invocations, and temporary health
suppression. Tune the bounded commit gate only from observed provider/runtime
fixtures and telemetry; provider output cannot override it.

MCP is not part of Phase 2A. A future MCP surface must remain a thin facade over
these Orac-owned retrieval services and authority decisions. Phase 2B now
accounts for the advertised schema and the final ephemeral tool exchange under
the shared effective context limit without changing Phase 2A authorization.

## Phase 2C: Authorised Domain Discovery

Phase 2C extends the existing coordinator and mediator. On each eligible turn,
Orac reads the principal's current authorised PROJECT catalogue through
`orac_code.rag_usage_authorization_api`, ranks only safe project metadata with
the dedicated `embedding.domain_discovery` profile, and advertises a bounded
shortlist. Descriptor vectors use a bounded in-process LRU whose identity
includes the profile, provider, model, dimensions, descriptor schema, registry
version, and descriptor digest. Cold descriptors are embedded in batches. A
routine catalogue above 128 projects does not disable discovery; the configured
absolute hard limit is an exceptional safety fallback for PROJECT discovery.

Conversation memory does not use generic descriptor matching. If compatible
principal-owned checkpoints exist and conversation retrieval is eligible, one
concise `Previous conversations` capability is advertised independently. This
avoids a preliminary memory search and permits natural topical recall without
explicit recall wording. PLUGIN discovery is narrower: it participates only
when the current host request already has a runtime-valid trusted retrieval
bridge. Installed plugins are not enumerated merely because they exist.

Each advertisement receives a random 96-bit opaque handle retained only in its
invocation's trusted offer. The Phase 2C tool accepts exactly `query` and a
non-empty, unique, bounded `domains` list whose values are schema-enumerated
handles. A forged, malformed, duplicate, unadvertised, or excessive selection
rejects the entire call before any adapter runs. Handles do not encode or grant
access to principals, project codes, plugin IDs, scope keys, conversation IDs,
or database selectors.

The host reauthorises each advertised binding immediately before its existing
adapter runs. A binding that becomes unavailable contributes no evidence and
receives only a generic unavailable status; other independently authorised
selections continue. PROJECT retains Oracle USE authorisation, CONVERSATION
retains principal ownership, and PLUGIN retains trusted identity and
`knowledge.self_scope_retrieval`.

Native adapter scores are retained for audit but never compared across domain
types. The deterministic merge takes rank 1 from each successful domain,
ordered by bounded domain weight, then orders remaining candidates by:

```text
domain_weight = 0.75 + 0.25 * normalised_discovery_score
weighted_rrf = domain_weight / (60 + within_domain_rank)
```

CONVERSATION uses the neutral weight `0.875`. Phase 2B accounts for the exact
catalogue instruction, tool schema, provider framing, response allowance, and
ephemeral tool exchange. If final headroom is tight, evidence is omitted from
the end of this deterministic ranking before the existing safety equation is
applied; no separate allocator is introduced.

Catalogue enumeration occurs per turn, so grants take effect without a new
conversation. Retrieval reauthorisation handles mid-turn revocation. Bounded
content-free telemetry records catalogue size, cache warmth and batches,
domains scored/advertised/selected, opaque handles and type/score/weight,
fallback mode, latency, candidate counts, unavailable-domain count, and final
evidence omission. It does not record queries, descriptors, prompts, evidence
text, or inaccessible domains.
