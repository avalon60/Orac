# Governed Semantic Retrieval

Eligible local model runtimes receive one read-only `retrieve` tool over
logical `CONVERSATION`, `PROJECT`, and `PLUGIN` domains. Orac remains the
security boundary. A model can provide only the retrieval query and one domain
from the exact schema advertised for that turn.

See [Conversation Context, Memory, and RAG](conversation-context-memory-and-rag.md)
for the operator-facing turn flow, shipped-state matrix, invocation examples,
and rollout checks.

## Shipped Effective State

The shipped `[governed_retrieval].enabled = true` initialises the coordinator,
but it does not make every model eligible. Exact governed capability evidence,
provider support, a positive model context limit, authorised domains, and
acceptable runtime health still resolve the effective mode.

Phase 2C discovery is active by default with
`domain_discovery_enabled = true` and `domain_discovery_shadow_mode = false`.
Shadow mode remains available only as an explicitly selected diagnostic or
development state.

Model-facing domain names and descriptions are routing metadata only. They are
not document evidence. Orac marks retrieval as required when the current turn
has bounded explicit local-retrieval intent or when discovery records at least
one authorised semantic domain above the configured threshold. The latter
covers ordinary questions such as `How does the fictional Atlas Finch scheduler
allocate work?` without query-specific keywords. Conversation availability
alone does not trigger required retrieval.

Required retrieval is a host decision, not an instruction the model may
override with prose. The tool decision receives compact governed policy, the
safe domain offer, and the current request. The complete ordinary prompt is
used only for the tools-disabled grounded answer after successful retrieval.
If the model omits a valid call, Orac retries once with stricter framing and
then reports retrieval as unavailable rather than committing an unsupported
answer.

The 32,768-token effective-context floor applies only to this advanced
model-controlled tool/discovery path. It does not disable the earlier explicit
host-mediated bounded knowledge route. Independent host switches can still
suppress an otherwise qualifying model: `enabled = false` disables governed
tools, while `domain_discovery_enabled = false` disables active Phase 2C
discovery. The shipped configuration keeps both active; an operator-selected
override is explicit in configuration and startup telemetry.

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

1. Provider-declared tools metadata is provisional and leaves the mode `NONE`.
2. Without bounded-probe-demonstrated `structured_tool_calling`, the mode is
   `NONE`.
3. With demonstrated structured evidence but without demonstrated streamed evidence, the mode
   is `BUFFERED`.
4. With bounded-probe-verified streamed capability evidence and compatible
   provider framing, the mode is
   `STREAMING` while operational streaming health remains acceptable.
5. Temporary framing-health suppression selects `BUFFERED` without changing
   authoritative model capability evidence.

`MODEL_METADATA_VERIFIED` verifies the provider's capability declaration for
the exact model revision; it does not claim demonstrated model behaviour.
Startup reconciliation records that provisional state, and only the fixed
bounded probes can promote it to `BOUNDED_PROBE_VERIFIED`. No model-name
allowlist is used.

The bounded host probes use only fixed fixture queries and never execute the
requested retrieval. Buffered structured behaviour is tested before streamed
behaviour. Transient provider or infrastructure failures retry at 10 and 30
seconds, for three attempts total per process and exact model revision. A
provider-completed invalid result is a genuine model rejection and is not
retried automatically.

Run the fixed probe against the configured local provider and model with:

```bash
.venv/bin/python scripts/probe_governed_retrieval.py --pretty
```

A successful startup probe is persisted through the narrow ORAC_CODE evidence
API. Transient failures never create evidence rows.

## ORAC_CORE Descriptor Validation

The former descriptor described only repository administration and did not
truthfully cover the authorised AI material ingested into `PROJECT:ORAC_CORE`.
The replacement is a general domain description, not query-specific wording.
Its canonical text is maintained in the
[descriptor seed](../resources/db/schema/orac_core/seed_data/zz_orac_core_project_descriptor.sql)
rather than duplicated here.

Using the shipped `domain_discovery` embedding profile, the replacement scored
the four positive fixtures at `0.629`, `0.679`, `0.678`, and `0.696`; the four
unrelated negative fixtures scored `0.283`, `0.339`, `0.322`, and `0.327`.
The positive set covered four representative in-domain architecture and
operations topics. The negative set covered four unrelated everyday topics.
All positives cleared the unchanged `0.50` threshold and no negative did.

Examples in this guide are deliberately fictional. `ORAC_DOCS` material can be
ingested into the same governed knowledge domain as user material, so repeating
real production regression questions here would make routing documentation a
competing evidence source. Executable tests retain the real regression wording
outside the searchable documentation corpus.

## Streaming Semantics

For a required turn, Orac never commits text from the tool-decision invocation.
It discards decision prose, accepts one valid call, and retries the compact
decision once if the model omits or malforms the call. A second failure returns
a host-authored retrieval-unavailable response. A valid call performs governed
retrieval and streams the existing full-context, tools-disabled grounded
continuation.

For an optional turn in `STREAMING` mode, the existing bounded commit gate
briefly retains visible assistant text. An early valid call discards that
buffered text, performs one governed retrieval, and streams a tools-disabled
final continuation. A direct answer is committed when either configured
character or delay threshold is reached and then continues through the
ordinary streaming path.

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

The broader review of flattened ordinary provider messages is tracked in
[Governed Retrieval Provider-Message Composition Follow-up](pending_work/governed-retrieval-prompt-composition-follow-up.md).

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
semantic matches, semantic advertisements, conversation-memory advertisements,
total advertised handles, required-retrieval reasons, decision attempts,
discarded decision character counts, selected opaque handles and
type/score/weight, fallback mode, latency, candidate counts,
unavailable-domain count, and final evidence omission. It does not record
queries, descriptors, prompts, discarded prose, evidence text, or inaccessible
domains.
