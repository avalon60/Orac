# Knowledge Model Evidence Submission

P1-08 is the Core-owned bridge between an approved P1-07 materialisation and
the existing primary flat-text model adapters. It supports verified UTF-8
Markdown, CSV, JSON, and plain text only. P1-06 remains the sole retrieval,
authorisation, verification, and managed-store boundary; P1-07 remains the sole
materialisation-level policy.

Raw-binary submission and model-capability routing remain deferred to Phase 2.
This Phase 1 adapter accepts only the authorised normalised text media above;
provider support for attachments does not widen that contract.

The feature ships enabled, but each turn remains gated to an eligible local text
model whose effective context is at least 32,768 tokens. It also requires
local-knowledge dialogue, P1-06 retrieval, and P1-07 materialisation to be
enabled. Ineligible models retain the existing bounded RAG path. No plugin,
APEX application, or adapter receives retrieval or storage access.

## Runtime flow

Explicit `summarise`, `review`, `extract`, `analyse`, or `compare` requests may
request materialisation after normal dialogue routing resolves one authorised
scope and RAG resolves exactly one document version. Ordinary knowledge Q&A
continues to use the existing bounded chunk grounding path.

Core then:

1. captures the authenticated principal, scope, exact model row, conversation,
   and policy fingerprint;
2. asks P1-07 for the narrowest acceptable representation and obtains content
   only through P1-06;
3. validates provenance and renders a canonical evidence envelope;
4. assembles the complete immutable prompt under the per-session turn lock;
5. rereads the same model row, checks the complete prompt budget, reauthorises
   through the database audit procedure, and records the submission decision;
6. invokes the selected adapter with strict output, endpoint, and retry options;
7. persists at most one assistant result and records one terminal outcome.

A model row change, disabled or unavailable model, missing context limit,
changed policy fingerprint, authorisation failure, unsupported media, invalid
provenance, or budget overflow fails closed. Core never changes model or
endpoint after P1-07 approval.

Classification enforcement allowlists the six current system-required
`DOC_CLASS` codes. Unknown or newly introduced codes are ineligible until the
Core policy and its tests explicitly approve them; evidence text and filenames
never determine classification.

## Canonical envelope

The wire form is exactly three physical lines:

```text
ORAC_UNTRUSTED_EVIDENCE_BEGIN version=1
<one canonical JSON line>
ORAC_UNTRUSTED_EVIDENCE_END version=1
```

JSON uses sorted keys, ASCII escaping, compact separators, and rejects non-finite
numbers. Evidence newlines, quotes, fences, role markers, formulas, and fake
boundary strings therefore remain characters inside JSON strings and cannot
create another outer delimiter. Parts retain the exact P1-07/P1-06 order and
are never sorted, omitted, or truncated.

Model-visible provenance is allowlisted. It may contain controlled numeric
document, version, extraction, artefact, chunk, and chunk-set identities plus
generic document labels and bounded worksheet, table, section, or A1-range
labels. It never contains filenames, source references, content URIs, storage
keys, filesystem paths, service URLs, principals, prompts, audit IDs, or content
hashes.

The trusted system policy and the short directive next to the envelope state
that all enclosed headings, HTML, CSV cells and formulas, role text, tool
requests, nested prompts, and exfiltration requests are untrusted data. Evidence
may supply facts but cannot alter tools, plugins, routing, model selection,
permissions, retrieval limits, or system instructions.

## Context accounting

P1-08 reuses the P1-07 conservative UTF-8 estimator, including its 20% uplift.
`M` is the lower of the governed registry context ceiling and an observed
provider runtime ceiling. If the runtime ceiling cannot be observed, Core uses
the governed ceiling and logs a safe warning. For effective maximum `M`:

```text
S = max(ceil(M * 0.05), 256)
O = 2048
U = M - S - O
E_cap = floor(U * 0.25)
```

The exact final prompt must not exceed `U`; the exact rendered envelope must
not exceed `E_cap`. The calculation includes the system primer, clock, user
facts, routing hints, web evidence, history, current user message, envelope,
and directives. A null, zero, stale, or sub-32,768 effective context limit is
ineligible. A request for more than 2,048 output tokens is rejected; a smaller
request still reserves and invokes with 2,048.

No evidence part is shortened to fit. Overflow requires a fresh P1-07
downgrade, a separately authorised bounded follow-up, or rejection.

## Retry, cancellation, and idempotency

Evidence submissions permit one retry only for a transient provider failure
before any response delta. The retry uses the byte-identical prompt, selected
model, endpoint, generation options, and output cap. Endpoint fallback and
automatic output-budget growth are disabled. Once output starts, failure is
terminal.

Voice cancellation bypasses the session turn lock so it can stop the active
stream. A cancelled evidence response is not saved as an assistant message.
Repeated protocol request IDs replay a stored assistant result and repair a
missing terminal audit outcome without invoking the model again.

## Bounded follow-ups

Follow-ups are disabled separately and are enabled only after initial rollout.
When enabled, Core retains only conversation, principal, scope, target and
registered artefact/chunk identities plus cumulative counters and expiry. It
does not retain evidence content, filenames, labels, paths, keys, or locators.

An explicit same-scope request must resolve the same registered document target,
repeat P1-06 authorisation, and pass P1-07 again. The cumulative ceilings are
two rounds after the initial request, 512 KiB, 24,000 conservative evidence
tokens, 16 members, 64 chunks, 2,000 CSV rows, and 120 seconds. P1-06's smaller
per-request limit always wins. Expired or different targets require a new
initial request or clarification; the model is not given a retrieval tool.

## Audit and diagnostics

`knowledge_retrieval_events` represents P1-08 with operation
`MODEL_SUBMISSION` and the existing `DECISION`/`OUTCOME` lifecycle. Oracle
constructs decision detail JSON from allowlisted scalar arguments and repeats
the current scope-authorisation check. The submission decision must reference a
completed approved or downgraded P1-07 decision.

Audit and normal logs retain only safe IDs/codes, counts, byte/token accounting,
flags, retry count, status, duration, and reason codes. They never retain
evidence content, prompts, model input/output, hashes, filenames, document or
spreadsheet labels, sensitive metadata, locators, or service URLs. Prompt dumps
are suppressed for every evidence turn, including failure paths.

## Rollout and rollback

P1-08 ships active for exact eligible local text models with an effective
context of at least 32,768 tokens. Models below that floor bypass P1-07/P1-08
and continue with existing bounded RAG. Review safe readiness and aggregate
metrics before lowering the floor, and enable follow-ups separately and last.

Set `[knowledge.model_evidence].enabled=false` to return immediately to the
existing RAG-only behavior. The database operation-code and package additions
are backward-compatible and remain inert.
