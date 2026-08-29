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
