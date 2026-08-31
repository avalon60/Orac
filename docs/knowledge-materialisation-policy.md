# Progressive Knowledge Materialisation Policy

P1-07 adds a Core-only policy layer above the P1-06 authorised normalised
content service. It does not submit content to a model; P1-08 owns the evidence
envelope and primary LLM integration. It never routes raw binary content.

## Levels and default

The ordered normalised levels are:

1. `METADATA_STRUCTURE`
2. `RELEVANT_CHUNKS`
3. `SURROUNDING_CONTEXT`
4. `LOGICAL_SELECTION`
5. `SELECTED_ARTEFACTS`
6. `COMPLETE_NORMALISED_DOCUMENT`

Question answering and bounded follow-ups default to relevant chunks. Structure
inspection defaults to metadata. Summarisation and review may request a complete
normalised document, but only after authorisation, registered-size accounting,
locality checks, and model-context checks. Extraction, analysis, and comparison
require a controlled selector or sufficient existing RAG evidence.

Complete documents are not enabled unconditionally. The shipped complete-
document limits are 256 KiB, 12,000 safety-adjusted evidence tokens, and 25% of
the currently usable model input context. These limits sit inside the P1-06
source, member, chunk, row, and emitted-byte ceilings.

## Decision contract

`ProgressiveMaterialisationPolicy` returns one of:

- `APPROVED`: the requested level is allowed;
- `DOWNGRADED`: a named narrower level must be used;
- `NEEDS_EVIDENCE`: another authorised bounded RAG retrieval is required;
- `REJECTED`: the request cannot proceed.

Results include the requested and effective levels, an ordered downgrade chain,
safe reason code, estimated bytes and tokens, usable context tokens, and
explicit `complete`, `selected`, `downgraded`, and `truncated` flags. P1-07
always sets `truncated=false`. Silent truncation is prohibited because it can
cut semantic units, falsify completeness, and detach evidence from provenance.
If a representation does not fit, the policy downgrades or rejects it.

The deterministic broad-to-narrow order is complete document, selected
artefacts, logical selection, surrounding context, relevant chunks, then
metadata. Authorisation and raw-binary failures reject rather than downgrade.
An ordinary relevant-chunk request with insufficient evidence returns
`NEEDS_EVIDENCE`; it does not silently become a metadata answer.

## Inputs and accounting

Trusted Core code supplies the authenticated principal, canonical authorised
scope, controlled target identity, purpose, optional requested level, registered
logical selector, existing RAG sufficiency, authorised metadata characteristics,
and a Core-derived model budget. A model budget includes `llm_id`, registry row
version, context policy, the lower of the governed registry maximum and any
observed provider runtime maximum, already occupied input, reserved output, and
explicit processing locality. A missing governed context maximum fails broad
materialisation closed. If runtime capacity cannot be observed, Core uses the
governed maximum and emits a safe warning.

`UTF8_CONSERVATIVE` version 1 estimates registered content before reading it and
re-estimates strict UTF-8 after P1-06 verification. The estimator uses a 20%
safety margin and per-part envelope overhead. Markdown/plain text and CSV/JSON
use separate conservative byte/character ratios. P1-08 must recalculate the
remaining budget immediately before model submission using the same registry
row version; a changed row version or smaller budget requires a fresh decision.

P1-06 still owns the hard caps: 256 metadata members, 32 selected artefacts, 64
chunks, 10,000 table rows, 8 MiB per source member, 16 MiB aggregate source, and
4 MiB emitted bytes. P1-07 configuration cannot widen those caps.

## Logical selectors

Selectors accept controlled database identities and registered provenance only:

- section: first and last chunk identities, returned as a verified source span;
- page range: positive page numbers, only when registered page provenance exists;
- sheet or table: registered artefact identities, never display names alone;
- artefact members: registered artefact identities;
- cell range: one registered table artefact identity plus a contained uppercase
  A1 rectangle;
- chunk range: first and last identities in one chunk set;
- surrounding context: anchor chunk identities plus zero to two chunks on each
  side by shipped policy (the retrieval contract has an immutable ceiling of
  eight).

Page selection currently rejects because P1-04/P1-06 do not register page
provenance. Worksheet and table names remain provenance returned to callers,
not lookup authority. No selector accepts filenames, storage keys, filesystem
paths, Oracle directory objects, or arbitrary SQL predicates.

## Classification and locality

Broad materialisation is local-model-only by default. P1-07 alone ships with
classification enforcement disabled. When P1-08 is enabled, Core supplies an
explicit allowlist containing the six current system-required `DOC_CLASS`
values (`RAW_REFERENCE`, `CONCISE_KNOWLEDGE_NOTE`,
`IMPLEMENTATION_DECISION_RECORD`, `TECHNICAL_MANUAL`,
`TROUBLESHOOTING_NOTE`, and `AUTOMATION_RULE_NOTE`). An unknown or newly added
classification therefore fails model materialisation closed until the policy
and tests are deliberately updated. The policy never infers sensitivity from
document text, filenames, or model output.

## Retrieval, audit, and failures

`KnowledgeMaterialisationCoordinator` reuses either the already authorised RAG
results or `KnowledgeMaterialisationService`. Managed store locators remain
private to P1-06. The coordinator verifies reused RAG chunk hashes and scopes,
performs post-verification token accounting, and reevaluates the policy before
returning parts. It does not introduce direct table or filesystem access.

The existing append-only `knowledge_retrieval_events` store records
`MATERIALISATION_POLICY` decisions. Oracle constructs `detail_json` from an
allowlist of codes, counts, flags, and accounting numbers. Audit rows never
store content, prompts, queries, filenames, worksheet/table labels, arbitrary
metadata, source references, storage keys, or paths. Audit failure fails closed.
Every new request reauthorises; an approved bounded P1-06 stream retains its
existing decision-time snapshot semantics.

Stable public policy reasons use the `MAT_*` namespace. Retrieval failures are
mapped to bounded policy reasons without database or filesystem details.

## Compatibility and rollout

P1-06 and P1-07 ship enabled. P1-07 still requires
`[knowledge.retrieval].enabled=true`, and P1-08 applies a per-model effective
context floor of 32,768 tokens. A selected model below that floor bypasses the
P1-07/P1-08 whole-content path for the turn; existing bounded RAG continues
normally. Existing searchable-chunk ranking, grounding, legacy CLOB
verification, Markdown artefacts, spreadsheet packages, plugins, APEX, and
model adapters remain unchanged. The switches remain independent rollback
controls: disabling P1-07 leaves P1-06 retrieval and existing RAG operational.
Database rollback removes only the additional audit operation constraint value
and the run-on-change package/view additions.

P1-08 consumes only an approved `ProgressiveMaterialisationResult`, captures
its immutable approval snapshot, and wraps every part as canonical untrusted
evidence. Bounded follow-up retrieval repeats authorisation and P1-07 policy
evaluation. See [Knowledge Model Evidence Submission](knowledge-model-evidence.md).
Phase 2 binary attachment routing must be a separate allowlisted capability and
must not reinterpret a P1-07 normalised level as binary permission.
