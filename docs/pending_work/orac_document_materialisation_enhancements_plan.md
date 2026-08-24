# Orac Document Materialisation and Binary Model Routing Enhancements

## Document purpose

This document is a planning brief for iterative use with Codex in plan mode.
It defines the goal, current-state findings, architectural constraints, phased
scope, development backlog, acceptance criteria, and questions that Codex must
resolve by inspecting the repository before proposing an execution plan.

The intended workflow is:

1. Submit this document to Codex in plan mode.
2. Require Codex to inspect the current repository, schema, APIs, runtime code,
   tests, configuration, documentation, and architectural guardrails.
3. Review the resulting Codex plan for omissions, unsafe assumptions, schema
   fit, and boundary violations.
4. Refine this brief or send corrective planning instructions to Codex.
5. Repeat until the execution plan is sufficiently precise and evidence-based.

This is not an execution instruction. Codex must not modify files, create
commits, or implement changes while responding to this planning brief.

## Goal

Enhance Orac so that ingested documents can be materialised safely for model
consumption beyond individual RAG chunks.

The near-term goal is to make complete or selected normalised content available
to the primary LLM in open textual formats, principally:

- GitHub-flavoured Markdown for narrative and semi-structured documents;
- CSV, accompanied by Markdown structure or manifest information, for
  spreadsheet tables;
- other explicitly approved textual derivatives where justified.

Orac must preserve and address both:

- the immutable original raw document; and
- one or more immutable normalised or derived representations.

The database must retain durable lineage and storage references for each
artefact. The content store must remain content-addressed and hash-sharded.
Model-facing code must resolve content through controlled document and artefact
identities, never through arbitrary caller-supplied filesystem paths.

A later, lower-priority phase will prepare Orac to submit original binary files
to models that can accept and use them. That phase must introduce
capability-aware model selection rather than a brittle direct mapping from MIME
type to one model.

## Scope summary

### Phase 1: Normalised document materialisation

Phase 1 is the near-term development priority. It must:

- verify and regularise storage of original raw documents;
- determine whether every accepted raw original is stored through the existing
  content-addressed hash-sharded mechanism;
- retain durable database references to raw originals;
- persist normalised artefacts on disk through a controlled hash-sharded store;
- retain durable database references, hashes, media types, sizes, provenance,
  and relationships for normalised artefacts;
- provide authorised retrieval and materialisation APIs for complete or
  selected normalised content;
- support safe submission of approved Markdown and CSV content to the LLM;
- enforce context, size, privilege, scope, and prompt-boundary controls;
- preserve current chunking, embedding, searchability, and provenance
  behaviour;
- avoid requiring a model to parse Office binaries for ordinary document use.

### Phase 2: Raw binary submission and capability-aware model routing

Phase 2 is documentation and design preparation only. It is not near-term
implementation scope. It must capture enough design detail that the future work
is not forgotten or accidentally constrained by Phase 1.

It must cover:

- binary attachment materialisation;
- model modality and MIME support declarations;
- capability-aware provider selection;
- privacy, locality, classification, cost, context, size, and availability
  policies;
- fallbacks to normalised representations;
- audit and provenance for binary submission;
- future database extensions required for maintainable routing.

## Current architecture and responsibility boundary

The current documented lifecycle establishes these ownership boundaries:

- Drop Box discovers files, validates them, hashes source content, performs
  format-specific normalisation, and submits the original plus canonical
  normalised content to Core.
- Core owns durable source storage, document lineage, extraction records,
  chunking, embeddings, tags, searchability, retrieval, authorisation, and
  grounding provenance.
- Plugins do not write directly to protected Core tables.
- Runtime and model-facing components use approved APIs and views.
- Original source documents, extracted text, tags, notes, and retrieved content
  are untrusted data, not instructions.

Phase 1 must preserve this boundary. Drop Box may understand source formats,
but Core must own durable artefact identity, storage registration,
authorisation, and model-facing materialisation.

## Current schema assessment

The supplied Core DDL and ingestion documentation show the following relevant
state. Codex must verify every finding against the current checked-out
repository before relying on it.

### Existing raw document representation

`orac_core.knowledge_document_versions` already records one document version
with:

- `content_sha256`;
- `content_uri`;
- `mime_type`;
- `original_filename`;
- `byte_size`;
- `source_modified_on`;
- `source_format_code`, added by the normalised metadata migration.

The current documentation states that Core copies the original source into a
managed content-addressed store using a path pattern equivalent to:

```text
sha256/<first-two>/<next-two>/<full-sha256>
```

This strongly suggests that the raw original is already intended to be an
immutable, hash-sharded, disk-resident payload and that `content_uri` points to
it.

However, Codex must inspect the implementation and prove:

- whether every successful managed-file capture stores the raw original using
  this scheme;
- whether `content_uri` is a relative managed-store locator, URI, or absolute
  filesystem path;
- whether path construction is centralised;
- whether hash verification occurs on write and retrieval;
- whether existing rows can contain plugin-owned or legacy paths;
- whether extensionless hash objects are deliberate and sufficient;
- whether orphan detection or reconciliation exists;
- whether a second copy can be created when identical bytes are submitted by
  different source documents;
- whether storage-root movement can occur without rewriting durable lineage.

### Existing normalised representation

`orac_core.knowledge_extractions` currently records:

- `document_version_id`;
- `extractor_code` and `extractor_version`;
- `text_sha256`;
- `extracted_text` as a required CLOB;
- `output_mime_type`, added by migration;
- `extractor_metadata_json`, added by migration.

`orac_core.knowledge_chunks` stores chunk text in a CLOB and now has
`chunk_metadata_json`.

This supports chunking and embeddings but does not, by itself, provide a durable
filesystem pointer to a complete normalised artefact. The normalised output is
currently represented principally as database CLOB content.

This is the principal Phase 1 schema gap.

### Existing lineage

The current relational chain is:

```text
knowledge scope
  -> source object
  -> document
  -> document version
  -> extraction
  -> chunk set
  -> chunk
  -> chunk embedding
```

The design already distinguishes a raw document version from an extraction.
That is a useful seam for introducing disk-backed normalised artefacts without
collapsing raw and normalised content into one record.

### Existing uniqueness and revision behaviour

Relevant uniqueness rules include:

- source objects unique by source type and source reference;
- one document per source object;
- document versions unique by document and raw content SHA-256;
- extractions unique by document version, extractor identity, extractor
  version, and normalised text SHA-256;
- chunk sets unique by extraction and chunking parameters.

Any new artefact model must preserve idempotency across retries and must not
create duplicate disk payloads or lineage rows for the same immutable bytes.

### Existing model registry

`orac_core.llm_registry` currently records:

- model identity and provider;
- model name;
- context policy and maximum context tokens;
- enabled state;
- a generic JSON `properties` column.

It does not expose a normalised relational model for:

- accepted input modalities;
- accepted binary MIME types;
- document or vision capabilities;
- attachment size limits;
- local-only or remote-processing policy;
- quality, cost, priority, or fallback routing.

The generic `properties` JSON may be useful for provider-specific details, but
Phase 2 planning must decide which routing facts require controlled relational
metadata and constraints.

## Core design principles

### 1. Store immutable content, not mutable working files

Both original and normalised artefacts should be immutable content-addressed
objects. A normaliser change or altered output creates a new derivative
artefact, not an in-place rewrite.

### 2. Use database identities at service boundaries

Callers should request content using identifiers such as:

- `document_version_id`;
- `extraction_id`;
- future `artefact_id` or equivalent;
- logical selectors such as sheet, table, page, section, or range.

Callers must not supply arbitrary content-store paths.

### 3. Keep storage locators implementation-safe

Codex must determine whether durable rows should store:

- a relative content-addressed locator;
- a storage object key;
- a URI with a controlled scheme;
- or another abstraction that allows the managed root to move.

Absolute host paths should not become durable business identity.

### 4. Separate canonical artefacts from request materialisation

The durable normalised representation is not the same thing as the subset
assembled for one LLM request.

For example, one spreadsheet may durably produce:

```text
workbook-manifest.md
sheet-sales-table-001.csv
sheet-forecast-table-001.csv
spreadsheet-metadata.json
```

A particular model request may materialise only:

```text
workbook-manifest.md
sheet-forecast-table-001.csv
```

### 5. Prefer normalised text for ordinary model consumption

Office and similar binaries should normally be converted before model use:

- document formats to Markdown;
- spreadsheets to a Markdown workbook manifest plus one or more CSV tables;
- presentations to Markdown plus optional rendered slides;
- audio to transcripts where speech content is sufficient;
- scanned or visually meaningful content to approved OCR or vision-derived
  text where necessary.

### 6. Use progressive disclosure

The model-facing retrieval protocol should support increasingly broad views:

1. document metadata and structure;
2. relevant chunks;
3. surrounding section, table, sheet, or page;
4. selected normalised artefacts;
5. complete normalised document when bounded and appropriate;
6. original binary attachment only in future Phase 2.

### 7. Policy remains authoritative

The LLM may request more evidence, but Core decides whether to approve,
downgrade, truncate, or reject the request based on:

- authenticated principal and active RAG usage privilege;
- canonical scope eligibility;
- document and artefact classification;
- context and token budgets;
- payload size limits;
- model capability;
- local or remote processing restrictions;
- configured routing policy;
- request purpose and auditability.

## Phase 1: Normalised document materialisation

### Phase 1 outcome

At completion, Orac must be able to locate, verify, authorise, and materialise
complete or selected normalised content from the managed store for submission
to the primary text LLM, while retaining the original raw document and all
existing RAG lineage.

Phase 1 does not require raw binary submission to an LLM.

### Phase 1 storage model questions for Codex

Codex must inspect the repository and recommend the least disruptive schema
that supports multiple immutable artefacts per document version or extraction.
At minimum, compare these approaches:

#### Option A: Extend `knowledge_extractions`

Add normalised content storage columns directly to each extraction, for
example hash, URI, byte size, and storage state.

Advantages:

- small schema change;
- natural ownership by extraction;
- straightforward for one normalised file per extraction.

Risks:

- weak fit for spreadsheet packages with a Markdown manifest plus multiple CSV
  artefacts;
- weak fit for future rendered pages, images, sidecars, and alternate
  normalisations;
- may overload one extraction row with package concerns.

#### Option B: Introduce a general knowledge artefact table

Create an immutable artefact entity related to document versions and/or
extractions, with fields conceptually covering:

- artefact identity;
- document version;
- producing extraction, where applicable;
- artefact role or type;
- media type;
- content SHA-256;
- storage locator;
- byte size;
- logical name;
- ordinal or parent artefact for packages;
- metadata JSON for bounded format-specific provenance;
- lifecycle or verification state;
- audit columns and row version.

Advantages:

- supports one raw original and many derivatives;
- supports Markdown, CSV, JSON, images, rendered pages, and future binary
  materialisations;
- provides a stable basis for Phase 2 without implementing Phase 2 routing.

Risks:

- greater migration and API surface;
- must avoid duplicating the current raw columns without a clear authority
  rule;
- requires carefully constrained artefact roles and relationships.

#### Option C: Introduce extraction output packages and members

Represent a normalisation as a package with one or more members.

Advantages:

- explicit fit for multi-table spreadsheets and rendered page sets;
- supports package manifests and member ordering.

Risks:

- potentially over-engineered for the first slice;
- may create avoidable complexity before spreadsheet ingestion exists.

Codex must not select an option solely from this brief. It must inspect current
capture, ingestion, retrieval, and API code and justify the selected design.

### Phase 1 raw storage requirements

The plan must include an explicit audit of raw original processing.

Codex must determine and document:

- where the managed root is configured and validated;
- how content hashes become shard paths;
- whether raw originals are copied atomically;
- whether temporary files are promoted by atomic rename;
- how concurrent identical submissions behave;
- whether the full hash is revalidated after promotion;
- whether database commit failure can leave an orphan;
- how orphan reconciliation should work;
- whether `content_uri` is sufficient as the durable pointer;
- whether raw object metadata requires a dedicated storage artefact row;
- whether all original media types, including future spreadsheets, follow the
  same sharding policy;
- whether a file extension is required for model attachments or can be added
  only to short-lived materialised copies;
- how path traversal, symlinks, and managed-root escapes are prevented.

Unless repository evidence proves otherwise, the default expectation is that
raw documents continue to use the existing content-addressed shard layout.
Raw documents should not receive a separate unsharded storage mechanism merely
because they may later be submitted to a model.

### Phase 1 normalised storage requirements

The selected design must support:

- a durable content SHA-256 for each normalised artefact;
- a durable managed-store locator;
- media type, byte size, producer identity, and producer version;
- relationship to the source document version and extraction;
- idempotent registration and reuse;
- one or many outputs from one extraction;
- a primary or manifest artefact designation where multiple members exist;
- logical ordering and bounded metadata for package members;
- verification that disk bytes match recorded hash and size;
- storage reconciliation and orphan handling;
- re-normalisation by a newer extractor version without overwriting history;
- continued availability of extraction CLOB data where needed for chunking or
  compatibility;
- a migration strategy if the CLOB eventually becomes optional or merely a
  cache;
- no forced duplication of very large normalised payloads in both CLOB and
  filesystem without a documented reason.

### Phase 1 model-facing materialisation protocol

Codex must plan a Core-owned API or service that supports controlled requests
such as:

```text
list_document_structure(document_version_id)
get_document_section(document_version_id, selector)
get_normalised_artefact(artefact_id)
materialise_normalised_document(document_version_id, requested_view)
```

These names are illustrative, not prescribed.

The protocol must support decisions equivalent to:

- approved as requested;
- approved with truncation;
- downgraded to selected sections or artefacts;
- rejected as unauthorised;
- rejected because the representation is unavailable;
- rejected because the content is too large;
- rejected because the target model cannot accept the materialisation.

The response should expose safe, auditable metadata such as:

- document and version identity;
- artefact identities and media types;
- included logical sections or tables;
- hashes;
- truncation status;
- token or byte estimates;
- safe decision and reason codes.

It must not expose unrestricted filesystem paths to the model.

### Phase 1 LLM submission requirements

The primary text model adapter must be able to receive approved normalised
content as bounded untrusted evidence.

The plan must address:

- how Markdown and CSV are represented in the model request;
- how multiple artefacts are delimited and labelled;
- how provenance is retained without copying whole documents into assistant
  metadata;
- how prompt injection boundaries are maintained;
- how token estimates are calculated before submission;
- how excessively large CSV files are sampled, partitioned, selected, or
  rejected;
- how the LLM can request additional logical sections without controlling disk
  access;
- how model-request materialisations are cleaned up if temporary files are
  used;
- whether text should be streamed from disk, loaded through a bounded service,
  or reconstructed from database content;
- how retrieval and complete-document requests interact with RAG usage
  privileges.

### Phase 1 spreadsheet preparation

Spreadsheet ingestion itself may be a separate development effort, but the
Phase 1 artefact design must not prevent it.

The plan should reserve a representation capable of supporting:

- a Markdown workbook manifest;
- one or more CSV files per logical table or sheet;
- stable sheet, table, and cell-range provenance;
- ordered package membership;
- optional metadata sidecars;
- formulas and cached values in metadata where available;
- selected-table materialisation rather than compulsory whole-workbook
  submission.

A workbook must not be flattened blindly into one CSV where that would lose
sheet or table identity.

## Phase 1 development backlog

Codex must convert these backlog items into a repository-specific execution
sequence with exact files, objects, APIs, tests, and dependencies.

### P1-01: Audit current raw managed-file storage

**Objective:** Prove how original documents are stored and referenced today.

**Status:** Completed on 26 July 2026. See the
[P1-01 raw managed-file storage audit](p1-01-raw-managed-file-storage-audit.md).

**Completion deliverables:**

- Record the verified current raw storage contract without fixing the future
  durable storage-key abstraction.
- Record the development database and filesystem observations and the read-only
  method used to reproduce them.
- Identify the exact Drop Box, Core runtime, schema, API, view, and grant seams.
- Separate confirmed defects, tentative inferences, and unresolved deployment
  questions.
- Define the required read-only environment preflight and its bounded report
  contents.
- Allocate every resulting implementation change to P1-02, P1-03, P1-05,
  P1-09, P1-10, or the separate least-privilege security decision.

**Acceptance criteria:**

- The audit names the exact implementation seams and schema objects.
- It records the verified current layout and clearly distinguishes observed
  state from future design decisions.
- It records correctness and security defects without implementing remediation.
- It defines the preflight requirements while assigning tool implementation to
  P1-09.
- It assigns lifecycle documentation and regression coverage to P1-10.
- P1-01 changes only audit and backlog documentation.

### P1-02: Select and document the normalised artefact data model

**Objective:** Define durable database lineage and disk pointers for
normalised outputs.

**Status:** Completed on 26 July 2026. See the
[P1-02 normalised artefact and chunk-lineage model](p1-02-normalised-artefact-data-model.md).

**Completion deliverables:**

- Compare extraction-column, general artefact, and package-member designs.
- Identify compatibility implications for existing extraction CLOBs.
- Define authority across raw document versions, extractor runs, normalised
  artefact members, compatibility CLOBs, chunk sets, and chunks.
- Define how each new chunk set identifies the precise normalised artefact it
  processed while retaining null compatibility for legacy CLOB-only rows.
- Define the composite relational constraint and artefact-aware idempotency key
  that prevent cross-extraction or cross-member chunk lineage.
- Define the durable storage-key abstraction for raw and normalised artefacts.
- Decide which storage-key properties belong in database shape validation and
  which require owning-API canonical validation.
- Define immutable locator authority, including whether an existing raw
  document-version locator may ever be changed.
- Define output-set atomicity, completeness, spreadsheet member metadata,
  constraints, indexes, lifecycle state, and idempotency keys.
- Define migration and rollback strategy.
- Record the exact downstream DDL, API, runtime, view, grant, and test seams
  without implementing them.

**Acceptance criteria:**

- The chosen model supports Markdown-only extraction and multi-file
  spreadsheet output.
- Raw and normalised artefacts have unambiguous ownership and lineage.
- MANIFEST and TABLE artefacts are independently chunkable and retrieval
  provenance identifies the exact member and source range.
- New output sets are registered atomically, require exactly one PRIMARY or
  MANIFEST, and cannot become searchable or materialisable while incomplete.
- The design avoids arbitrary absolute paths.
- Hash, media type, byte size, and producer provenance are mandatory where
  appropriate.
- The durable key is `sha256:<lowercase-hash>` and no database constraint
  hard-codes the physical hash-shard path.
- Legacy shard locators remain compatible through P1-03 dual resolution and
  migrate only through the controlled P1-05 exception.
- The plan includes exact DDL files and Liquibase sequencing.
- P1-02 changes only design and backlog documentation.

### P1-03: Implement or regularise the managed artefact store abstraction

**Objective:** Ensure raw and normalised content use one controlled storage
abstraction.

**Status:** Completed on 26 July 2026.

**Delivered:**

- Added the Core-owned streaming managed store in
  `src/orac_core/knowledge/managed_store.py`.
- Made `[knowledge].managed_root` authoritative for capture and worker
  instances, with fixed root identity, permission, filesystem, and hard-link
  capability validation.
- Added logical-key writes, legacy/logical dual reads, descriptor-relative
  no-follow traversal, same-descriptor hash-and-size verification, and atomic
  hard-link promotion with installed-versus-reused outcomes.
- Kept raw and future normalised bytes in one global content-addressed pool.
- Made Drop Box capture stream a containment-authorised, stable regular-file
  descriptor into the store.
- Prevented ordinary runtime mutation or deletion of immutable raw
  document-version identity and provenance.
- Added stable permanent/transient worker failure mapping and fail-closed
  service configuration handling.
- Added an executable repository guard that reserves runtime physical shard
  construction and resolution to the managed-store module.
- Added bounded store facts and reference inspection for P1-09 without adding
  inventory, reconciliation, repair, or cleanup policy.

**Acceptance criteria:**

- Callers cannot provide arbitrary destination paths.
- Identical bytes are stored idempotently.
- Hash and size are verified at registration and retrieval boundaries.
- Storage-root relocation does not require changing document identity.
- Concurrent writes do not leak temporary files or expose partial payloads.
- Tests cover concurrent writes, interrupted promotion, corruption, configured
  root consistency, safe locator resolution, and temporary cleanup.

### P1-04: Persist normalised outputs as managed artefacts

**Objective:** Register normalised Markdown and future CSV outputs on disk and
in the database.

**Status:** Completed on 12 August 2026.

**Delivered:**

- Added immutable extraction-owned `knowledge_artefacts`, insert-only API
  registration, output-set completeness, canonical UTF-8 identity checks, and
  root-independent managed storage keys.
- Made capture persist canonical Markdown beside the raw original and register
  the complete SINGLE output set in the ingestion transaction.
- Added nullable artefact lineage to chunk sets, including a composite
  same-extraction foreign key and artefact-aware idempotency.
- Made the worker verify managed PRIMARY, MANIFEST, and TABLE bytes before
  source-specific chunking; spreadsheet CSV is split only at complete record
  boundaries and retains worksheet row and cell-range provenance.
- Kept legacy null-artefact chunk sets readable while making incomplete new
  output sets non-searchable and impossible to complete.
- Exposed exact artefact and spreadsheet provenance through searchable chunks,
  retrieval models, and grounding provenance.
- Added capture, worker, CSV, schema, and live rollback-only database coverage.
  Operational diagnostics use the existing ingestion request/event pathway;
  adoption of a separate PL/SQL Logger framework remains deferred because it
  is not installed in the repository or development database.

**Work:**

- Extend capture or ingestion flow to write immutable normalised artefacts.
- Register one extraction's complete output set in one database transaction,
  with exactly one PRIMARY or MANIFEST and idempotent all-member reuse.
- Register hashes, media types, sizes, producer identity, deterministic logical
  names, ordered membership, and bounded spreadsheet metadata.
- Add nullable `knowledge_chunk_sets.source_artefact_id`, enforce membership
  in the same extraction, and create independent chunk sets for MANIFEST and
  TABLE members.
- Preserve current chunking input and completion invariants.
- Treat extraction CLOB text as a transitional compatibility projection and
  legacy input; require PRIMARY or MANIFEST managed bytes to match its
  canonical UTF-8 identity.
- Assert complete artefact sets before request completion and keep incomplete
  sets non-searchable.
- Preserve retry idempotency.

**Acceptance criteria:**

- A newly ingested supported document has a verifiable raw storage reference
  and at least one verifiable normalised storage reference.
- Repeating the same capture does not duplicate lineage or disk content.
- A changed extractor version can create a new derivative without changing the
  raw document version.
- Two CSV members from one extraction can be chunked with the same chunker
  configuration without sharing a chunk-set identity.
- A failed output-set registration commits no partial member rows.
- Existing ingestion and retrieval tests remain valid or are intentionally
  migrated.

### P1-05: Backfill or migration strategy for existing extractions

**Objective:** Make existing database-held normalised content compatible with
new disk-backed retrieval.

**Status:** Completed on 13 August 2026.

**Delivered:**

- Added a reusable, dry-run-first `orac-knowledge` operator command with
  read-only preflight, bounded extraction backfill, and controlled raw-locator
  migration operations.
- Implemented the P1-09 preflight subset required by this migration: bounded
  candidate classification, safe reference verification, machine-readable
  reason codes, and non-sensitive managed-store facts. Full orphan,
  stale-temporary-file, and physical inventory reconciliation remains P1-09.
- Added a least-privilege ORAC-only migration API with one-item transaction
  boundaries, append-only migration events, and a narrowly constrained
  legacy-shard-to-logical locator exception.
- Backfilled the development environment in two bounded batches. All 43
  canonical legacy extractions now have complete managed PRIMARY artefacts and
  artefact-owned existing chunk sets; no re-chunking or re-embedding occurred.
- Verified that all 43 development raw locators were already logical, so no raw
  locator rows required mutation.

**Work:**

- Run the P1-09 read-only preflight in each target environment before
  migration.
- Classify legacy, absolute, plugin-owned, or otherwise noncanonical raw
  locators and storage layouts.
- Prove the corresponding bytes and intended managed object before any raw
  locator rewrite.
- Determine whether existing extraction CLOBs should be backfilled into the
  managed store as complete output sets.
- Migrate proven raw shard locators to logical keys as an explicit one-time
  exception to normal raw-version immutability.
- Define resumable, idempotent migration behaviour.
- Define validation and reporting for missing or corrupt originals.
- Avoid making deployment depend on an unbounded one-shot migration.

**Acceptance criteria:**

- The plan clearly distinguishes mandatory deployment migration from optional
  operational backfill.
- Raw locator and store-layout compatibility is explicit for every inspected
  environment.
- No existing locator is rewritten solely from its textual shape.
- Ordinary runtime reuse never mutates raw locator, hash, MIME type, byte size,
  or source format after the controlled migration.
- Existing searchable documents remain searchable during transition.
- Backfill can resume safely after interruption.
- Counts and safe failure reasons are reportable.

### P1-06: Add authorised document and artefact retrieval APIs

**Objective:** Retrieve raw metadata and normalised content through controlled
Core interfaces.

**Status:** Completed on 13 August 2026.

**Delivered:**

- Added a scope-first, principal-authorised `ORAC_CODE` retrieval package that
  returns bounded metadata, managed member descriptors, legacy CLOB content,
  and searchable chunks only after a current Oracle `USE` decision.
- Added append-only retrieval decision/outcome auditing without content,
  filenames, metadata JSON, storage keys, locators, or physical paths.
- Added Core Python materialisation for complete normalised content, selected
  members, UTF-8 text ranges, chunk-anchored sections, chunk ranges, and
  worksheet/table A1 ranges with full source verification and emitted hashes.
- Cut existing dialogue RAG over to the authorised cursor while retaining its
  scoring, searchable-chunk, grounding, and provenance behaviour.
- Retired `allow_all_scopes`, removed the runtime searchable-view and broad
  artefact-package access, removed the plugin bridge's broad ingestion grant,
  and dropped the obsolete runtime synonym.
- Preserved explicit legacy/null artefact provenance and the P1-04/P1-05
  lineage without re-chunking or re-embedding. Raw binary retrieval remains a
  separate Phase 2 attachment concern.

**Work:**

- Define approved API ownership across `ORAC_CORE`, `ORAC_API`, `ORAC_CODE`,
  runtime, plugin bridge, and APEX layers.
- Resolve by document or artefact identity, never by caller path.
- Enforce scope and principal authorisation.
- Return streams or bounded payloads with verification metadata.
- Return exact artefact role, logical member, workbook, sheet, table,
  member-range, and chunk-range provenance where available.
- Preserve explicit null artefact provenance for legacy CLOB-backed chunks.
- Audit retrieval decisions without persisting full content in audit rows.

**Acceptance criteria:**

- Unauthorised principals cannot retrieve content by guessing identifiers.
- APIs reject corrupt, missing, or root-escaping storage locators.
- Retrieval records safe provenance and reason codes.
- Direct protected-table or filesystem access is not added to plugins.

### P1-07: Add progressive normalised materialisation policy

**Status:** Implemented behind disabled feature flag on 14-Aug-2026. See
`docs/knowledge-materialisation-policy.md`.

**Objective:** Decide how much content may be exposed for one model request.

**Work:**

- Define supported materialisation levels.
- Use user intent, retrieval sufficiency, document characteristics, size,
  context budget, and policy.
- Support approval, downgrade, truncation, and rejection decisions.
- Define logical selectors for sections, pages, sheets, tables, and ranges where
  available.

**Acceptance criteria:**

- Whole-document materialisation is not the unconditional default.
- Small complete documents can be supplied when authorised and within budget.
- Large documents are reduced to selected artefacts or sections.
- Decisions are deterministic enough to test and audit.

### P1-08: Integrate Markdown and CSV with the primary LLM adapter

**Status:** Implemented behind disabled feature flags on 14-Aug-2026. See
`docs/knowledge-model-evidence.md`.

**Verified implementation notes:** No architecture deviation was required.
The repository contains the backward-compatible constraint/package delta, but
the development database was intentionally inspected read-only rather than
deployed during P1-08 implementation. Invocation rollout remains blocked until
eligible enabled local model rows have verified positive context limits; all 20
currently enabled rows still have `MAX_CONTEXT_TOKENS = NULL`. Follow-ups use
explicit same-scope requests resolved back to the registered document target;
no model tool or model-prose retrieval parser was introduced.

**Objective:** Submit approved normalised content to the existing text model.

**Work:**

- Define a stable evidence envelope for multiple Markdown and CSV artefacts.
- Preserve source labels and artefact provenance.
- Enforce model context policy and token budgets.
- Keep document content in the untrusted evidence boundary.
- Permit bounded follow-up requests for additional sections or tables.

**Acceptance criteria:**

- The adapter can answer from a complete small Markdown document without
  relying only on RAG chunks.
- The adapter can consume a selected CSV table with its workbook or table
  context.
- Prompt injection tests prove that document text is not treated as privileged
  instruction.
- Oversized materialisation is safely downgraded or rejected.

### P1-09: Add operational reconciliation and observability

**Objective:** Make disk/database divergence visible and recoverable.

**Status:** Deployed and operationally verified in development on 15-Aug-2026.
The specification and body are `VALID`; the only package privilege is
non-grantable `EXECUTE` to `ORAC`, and both bounded inventory cursors execute
successfully through that runtime account.

The development reconciliation currently returns `BLOCKED` because its
disposable managed store contains confirmed orphan candidates and stale
temporary entries. That result is an operational diagnostic, not a P1-10
prerequisite, and no cleanup or managed-store mutation is implied.

**Delivered:**

- Added independent `orac-knowledge reconcile` human and version-one JSON
  contracts without changing P1-05 migration-preflight semantics.
- Added a bounded ORAC-only, read-only reconciliation package that streams
  registered payload and lineage inventories through existing ORAC_API views.
- Added descriptor-oriented, non-following, deterministic physical inventory
  in the Core managed-store module, including full canonical-object hashing,
  temporary-file accounting, layout/type/permission checks, and root/directory
  stability checks.
- Added before/after Oracle snapshot comparison without holding a database
  transaction across filesystem work.
- Added stable `READY`, `BLOCKED`, and `INCOMPLETE` semantics, resource ceilings,
  safe retry classification, bounded numeric database samples, and redacted
  state fingerprints.
- Kept audit persistence, repair, quarantine, deletion, locator rewriting,
  content recovery, APEX, plugins, and model tools outside P1-09.

**Work:**

- Implement the reusable read-only environment preflight specified by the
  P1-01 audit.
- Report the managed-root configuration source and opaque compatibility facts,
  never the configured or resolved path, together with database counts,
  locator classifications, shared payloads, missing or unreadable objects,
  hash and size mismatches, malformed layouts, unsafe paths, and symlinks.
- Add inventory and safe checks for corrupt, unregistered, and orphaned
  artefacts.
- Report incomplete output sets and artefact-to-extraction or
  chunk-set-to-artefact lineage mismatches.
- Report stale temporary-file counts, ages, sizes, and distinct hashes.
- Report filesystem compatibility facts needed by the selected atomic
  promotion mechanism.
- Define metrics and bounded event or status reporting.
- Consider an administrator-facing report only if consistent with current APEX
  boundaries and priorities.
- Ensure raw paths and sensitive host details are not exposed unnecessarily.

**Acceptance criteria:**

- Operators can distinguish database lineage failure from missing disk content.
- The initial preflight and reconciliation mode is strictly read-only.
- Reports provide bounded human-readable summaries, machine-readable reason
  codes, and non-sensitive diagnostics.
- Any quarantine, repair, or deletion action is separately approved, explicit,
  and auditable.
- No unrestricted directory listing is exposed through APEX or model tools.

P1-09 makes divergence safely diagnosable for a future approved recovery
workflow. It does not itself implement repair, quarantine, deletion, locator
rewriting, or content recovery.

### P1-10: Update documentation and regression coverage

**Objective:** Make the new lifecycle maintainable.

**Status:** Completed on 15-Aug-2026 without database deployment or managed-store
mutation.

**Delivered:**

- Updated Core ingestion, maintenance, configuration, and Drop Box operator and
  lifecycle guides to describe the implemented raw, normalised artefact,
  extraction, chunk, retrieval, materialisation, and reconciliation authority
  boundaries.
- Documented bounded configuration, `READY`/`BLOCKED`/`INCOMPLETE` semantics,
  concurrency and interrupted-promotion classification, redaction, and the
  separately authorised recovery boundary without advertising automatic repair.
- Added deterministic isolated regression coverage for database registration
  failure after promotion and retry reuse, configured alternate roots, exact
  spreadsheet provenance, UTF-8/BOM/newline compatibility, and documentation
  contracts, while retaining the existing concurrency, corruption, traversal,
  symlink, retrieval, reconciliation, and model-adapter suites.
- Added a rollback-only, controller-excluded Oracle acceptance script for
  output-set atomicity, artefact-backed chunk-set idempotency, cross-extraction
  denial, `MANIFEST`/`TABLE` behaviour, legacy null sources, incomplete-set
  denial, and retry after rejected registration.
- Kept Phase 2 raw-binary submission and model-capability routing deferred.

**Work:**

- Update document ingestion and Drop Box lifecycle documentation.
- Document raw and normalised artefact authority.
- Document configuration, limits, recovery, and security behaviour.
- Document the implemented inventory, corruption, stale-temp, orphan, and
  reconciliation lifecycle.
- Add schema, API, worker, storage, retrieval, reconciliation, and model-adapter
  tests.
- Cover identical-content reuse, concurrent promotion, interrupted promotion,
  alternate roots, hash and size mismatch, path escape, symlinks, database
  failure after promotion, retry reuse, and reconciliation reporting.
- Cover artefact-backed chunk-set idempotency, cross-extraction rejection,
  MANIFEST versus TABLE chunking, legacy null sources, incomplete-set denial,
  exact spreadsheet provenance, and UTF-8/BOM/newline compatibility.

**Acceptance criteria:**

- Documentation reflects implementation rather than intended behaviour only.
- Architecture boundaries and unsupported capabilities are explicit.
- Phase 2 remains documented as deferred and is not accidentally advertised as
  available.

### Separate security decision identified by P1-01

**Status:** Resolved by P1-06. The broad `ORAC_PLUGIN` ingestion-package grant
was revoked; the current runtime path uses `ORAC`, and reconciliation adds only
non-grantable package `EXECUTE` for `ORAC`.

**Historical finding:** `ORAC_PLUGIN` had execute on the complete
`orac_code.knowledge_ingestion_api` package.

**Required decision:**

- Retain the grant with an explicit least-privilege justification;
- replace it with a narrower package or status interface; or
- revoke it after removing the dependency.

This decision is not part of P1-01 implementation, and P1-01 makes no grant or
runtime change.

## Phase 1 completion criteria

Phase 1 is complete only when all of the following are demonstrated:

- The original raw document remains immutable and hash-addressed on disk.
- The database has a durable, validated reference to the raw original.
- At least one complete normalised artefact is immutable and hash-addressed on
  disk.
- The database has durable, validated lineage and a storage reference for the
  normalised artefact.
- Existing chunk and embedding lineage remains connected to the producing
  extraction.
- An authorised request can materialise bounded normalised content by database
  identity.
- The primary text LLM can receive Markdown and CSV evidence without direct
  filesystem access.
- Unauthorised, oversized, corrupt, missing, or context-exceeding requests fail
  closed or are safely downgraded.
- Storage and database reconciliation behaviour is tested.
- Existing Drop Box and Core ingestion behaviour remains compatible or has an
  explicit migration path.

## Phase 2: Raw binary submission and model capability routing

### Priority and delivery status

Phase 2 is lower priority and must not be scheduled as near-term development
unless separately approved. The immediate objective is to preserve concepts,
requirements, and likely schema direction.

Phase 1 should avoid choices that make Phase 2 unnecessarily difficult, but it
must not build an elaborate routing platform before there is an approved use
case and model inventory.

### Phase 2 goal

Allow Orac to materialise an authorised original or derived binary file and
submit it to a suitable model or specialist provider when binary or multimodal
analysis provides value beyond the normalised representation.

Examples include:

- rendered pages for scanned documents or diagrams;
- spreadsheet dashboard images where colour and layout convey meaning;
- original PDF submission to a provider with verified PDF support;
- image, audio, or video input to a compatible specialist model;
- original Office binary submission only where the serving stack and model
  genuinely support it and policy permits it.

### Capability routing model

Do not implement a direct and exclusive `media_type -> model_id` association.
MIME type describes the container but does not fully describe the work.

The future routing decision should combine:

```text
required capabilities =
    media-type defaults
    + detected document characteristics
    + user-request requirements
```

The stable behavioural vocabulary is now controlled by
[`p2-02-controlled-capability-taxonomy.md`](p2-02-controlled-capability-taxonomy.md)
and the completed P2-02 record below. Earlier illustrative transport-oriented
or overly broad examples are superseded; MIME acceptance, context size, tool
calling, file transport, and code execution are not silently treated as the
document/media behaviours defined by P2-02.

A capability provider may be:

- an LLM;
- a vision-language model;
- an OCR engine;
- a speech-to-text engine;
- a document parser;
- Oracle SQL;
- a controlled Python analysis service;
- another deterministic tool.

### Phase 2 database design considerations

Codex should document a future relational design covering at least:

#### Media-type processing policy

Conceptual attributes:

- media type or controlled media pattern;
- default normaliser or processor;
- canonical output format;
- binary submission eligibility;
- default processing strategy;
- enabled state and priority.

#### Capability catalogue

Conceptual attributes:

- stable capability code;
- description;
- capability class;
- active state;
- whether the provider is deterministic or model-based.

#### Provider capability association

Conceptual attributes:

- provider or model identity;
- capability code;
- declared modality;
- supported MIME type or pattern where applicable;
- maximum bytes, pages, frames, duration, or tokens;
- quality or suitability tier;
- priority;
- active state;
- provider-specific properties.

#### Routing policy

Conceptual attributes:

- request or route class;
- required capability;
- preferred and fallback provider ordering;
- local-only requirement;
- remote-processing permission;
- maximum cost class;
- minimum quality tier;
- classification ceiling;
- availability and health requirements;
- active and effective dates.

#### Submission audit

Conceptual attributes:

- authenticated principal;
- document version and artefact;
- selected provider and model;
- required and satisfied capabilities;
- submitted media type and byte size;
- policy decision and safe reason code;
- locality and classification decision;
- start, completion, and failure timestamps;
- hashes and provenance without storing duplicate binary payloads.

### Phase 2 binary materialisation requirements

A future binary materialisation service must:

- resolve an authorised artefact by database identity;
- verify recorded hash and byte size before submission;
- create a short-lived filename or attachment with an appropriate extension
  only when the client API requires one;
- avoid exposing the managed-store path;
- enforce provider size and modality limits;
- clean up temporary materialisations;
- prevent content from being sent to remote providers when policy requires
  local processing;
- record the exact provider, model, media type, hash, and decision provenance;
- fall back to normalised Markdown, CSV, transcript, or rendered selections
  when binary submission is unsupported or inappropriate.

### Phase 2 routing considerations

Future planning must address:

- how declared model capabilities are validated rather than trusted blindly;
- the difference between a serving API accepting a file and the underlying
  model understanding that file;
- health and availability of specialist models;
- GPU memory contention and model-loading latency;
- whether the primary model remains the response orchestrator;
- whether specialist output is structured evidence returned to the primary
  model;
- privacy classification and remote-provider restrictions;
- cost and rate limits;
- deterministic structured calculation for spreadsheet arithmetic instead of
  model substitution;
- fallback order when a preferred provider is unavailable;
- auditability and reproducibility of routing decisions;
- configuration and APEX maintenance without exposing unsafe provider details.

## Phase 2 development backlog

These are future backlog tickets. They should be documented but not included in
near-term execution unless separately authorised.

P2-08 is a viability and decision gate, not an assumed bridge to P2-09 and
P2-10. P2-09 and P2-10 are contingent placeholders only. Their presence in the
backlog does not authorise them, establish that they are necessary, or imply
that they will proceed. Do not produce detailed P2-09 or P2-10 plans until
P2-08 has been implemented and accepted.

For every final activity below, return the next-step plan as a self-contained,
copy/paste-ready Markdown object in its own fenced block. It must be usable to
start a fresh Codex planning session without relying on the current chat and
must include the source-plan path, planning-only constraint, current resolved
evidence, objectives, required repository inspection, deliverables, acceptance
criteria, and explicit in-scope and out-of-scope boundaries.

### P2-01: Catalogue binary and multimodal use cases

Identify concrete cases where normalised Markdown or CSV is insufficient.
Record expected media types, security classification, payload sizes, provider
options, and fallback behaviour.

**P2-01 completed: 22-Aug-2026.**

The evidence-backed planning catalogue is
[`p2-01-binary-multimodal-use-case-catalogue.md`](p2-01-binary-multimodal-use-case-catalogue.md).
It evaluated all eight initial use cases and the required negative cases:

- `CANDIDATE`: `UC-PDF-SCAN`, `UC-PDF-VISUAL`,
  `UC-IMAGE-TECHNICAL`, `UC-SPREADSHEET-VISUAL`,
  `UC-PRESENTATION-VISUAL`, and `UC-AUDIO-SPEECH`;
- `VALIDATED`: none; there are no approved representative fixtures paired
  with an evidenced user outcome that normalised Markdown or CSV cannot serve;
- `DEFERRED`: `UC-VIDEO-TEMPORAL` and `UC-OFFICE-ORIGINAL`;
- `REJECTED`: no positive use-case ID. The catalogue rejects adequate
  Markdown/CSV replacements, arbitrary provider-accepted files,
  model-performed spreadsheet arithmetic, unsafe/active/encrypted containers,
  caller-supplied paths or managed keys, policy-free remote processing,
  unbounded submissions, and reuse of interactive voice as knowledge
  ingestion.

There are no validated use cases in P2-01.

The priority ordering passed to P2-02 is:

1. deterministic inspection and bounded selection for every media family;
2. Tier 1 PDF inspection/rendering/OCR, selected PDF/image interpretation, and
   deterministic spreadsheet parsing/calculation plus selected chart/layout
   interpretation;
3. Tier 2 presentation extraction/rendering and bounded local speech
   transcription;
4. Tier 3 video-temporal behaviour and direct Office-original handling remain
   deferred.

Unresolved evidence includes representative fixtures, measured expansion and
derived-output envelopes, fixture ownership, and demonstrated
normalisation-insufficient user outcomes. Current `DOC_CLASS` values remain
content-purpose classifications rather than sensitivity policy; remote
processing remains ineligible until the separate locality and sensitivity
policy is approved. Official Ollama and LM Studio image-input mechanisms were
checked on 22-Aug-2026, but no registered underlying multimodal model was
verified and the configured Ollama endpoint was unavailable for a bounded
metadata-only probe.

P2-01 added documentation and structural regression coverage only. No binary
runtime support was enabled, and no database object, configuration, privilege,
provider adapter, plugin capability, managed-store content, model, or deployed
service was changed. P2-03 through P2-10 remain not started.

**Final activity after resolution:** Return to
[@orac_document_materialisation_enhancements_plan](thread://019ff810-7695-7282-84e4-5fce86936a56)
and produce a decision-complete plan for P2-02, using the resolved P2-01 use-case
catalogue as evidence. Return it in the copy/paste-ready form required above.
Do not implement P2-02 during that planning activity.

### P2-02: Define controlled capability taxonomy

Create stable capability codes and distinguish deterministic tools from model
providers. Avoid provider names in capability semantics.

**P2-02 completed: 22-Aug-2026.**

The controlled provider-neutral taxonomy is
[`p2-02-controlled-capability-taxonomy.md`](p2-02-controlled-capability-taxonomy.md).
It is a planning and P2-03 input document under `pending_work`, not an operator
guide or feature-availability statement.

The final capability classes are:

- `PRIMARY_TEXT_REASONING`;
- `DETERMINISTIC_INSPECTION`;
- `DETERMINISTIC_TRANSFORMATION`;
- `DETERMINISTIC_CALCULATION`;
- `SPECIALIST_INTERPRETATION`.

The final stable capability codes are:

- foundational: `text_reasoning`, `container_inspection`, and
  `bounded_media_selection`;
- document/image: `layout_extraction`, `page_rendering`,
  `ocr_text_extraction`, `document_visual_interpretation`,
  `technical_image_interpretation`, and `chart_visual_interpretation`;
- spreadsheet: `workbook_structured_extraction`, `spreadsheet_calculation`,
  and `sheet_chart_rendering`;
- presentation: `presentation_structured_extraction`, `slide_rendering`, and
  `presentation_visual_interpretation`;
- audio: `audio_metadata_inspection`, `speech_transcription`,
  `speaker_diarisation`, and `audio_semantic_interpretation`;
- video: `video_metadata_inspection`, `subtitle_extraction`,
  `keyframe_extraction`, and `video_temporal_interpretation`.

Each code names one behaviour rather than a MIME type, transport field,
provider, model, implementation, or enabled state. Every record defines the
accepted source/derived representation, required characteristics, structured
output evidence, authority, selection, provenance, bound dimensions, locality,
fallback, evidence status, related use cases, deferred behaviour, and P2-03
metadata note. `speech_transcription` is specialist interpretation even when it
is required by the audio use case; required behaviour is not automatically
deterministic. OCR remains a controlled versioned transformation with explicit
uncertainty. Deterministic spreadsheet parsing and calculation remain
authoritative, and the primary text model consumes structured evidence without
silently replacing source or deterministic facts.

The P2-01 mapping resolved as follows:

- `UC-PDF-SCAN` requires inspection, bounded selection, page rendering, OCR,
  and final text reasoning; document visual interpretation is optional.
- `UC-PDF-VISUAL` requires inspection, layout extraction, bounded selection,
  page rendering, and final text reasoning; document/chart interpretation is
  optional.
- `UC-IMAGE-TECHNICAL` requires inspection, bounded selection, OCR, and final
  text reasoning; technical-image interpretation is optional.
- `UC-SPREADSHEET-VISUAL` requires inspection, workbook extraction,
  deterministic calculation, bounded selection, sheet/chart rendering, and
  final text reasoning; chart interpretation is optional.
- `UC-PRESENTATION-VISUAL` requires inspection, presentation extraction,
  bounded selection, slide rendering, and final text reasoning;
  presentation/chart interpretation is optional.
- `UC-AUDIO-SPEECH` requires audio inspection, bounded selection,
  transcription, and final text reasoning; diarisation and broader audio
  interpretation remain optional and evidence-pending.
- `UC-VIDEO-TEMPORAL` retains metadata inspection, selection, subtitles,
  transcription, keyframes, and temporal interpretation as documented but
  deferred behaviour.
- `UC-OFFICE-ORIGINAL` retains container inspection plus format-specific
  deterministic extraction/rendering; direct original-container
  interpretation remains deferred.

The evidence-state vocabulary passed to P2-03 is `UNASSESSED`,
`API_DECLARED`, `MODEL_METADATA_VERIFIED`, `BOUNDED_PROBE_VERIFIED`, and
`REJECTED`. These states apply to dated provider/model/capability associations,
not taxonomy existence, runtime enablement, or health. Official Ollama and LM
Studio image mechanisms checked on 22-Aug-2026 remain `API_DECLARED` transport
evidence only. The configured Ollama endpoint was still unavailable for a
metadata-only probe; no exact underlying model/revision was metadata- or
probe-verified, and no model was downloaded, loaded, or invoked.

A read-only development query reconfirmed 20 enabled `ollama` registry rows,
all with effective model type `TEXT`; all 20 JSON property objects omitted
`model_type`. Counts and types match P2-01, no row was created or updated after
the P2-01 evidence date, and same-day ordering remains unknowable because the
P2-01 baseline recorded no exact query timestamp. No Core capability/modality
table or view exists. Deployed artefacts comprised 60 Markdown `PRIMARY` rows.
The mapped application saved connection was unavailable, so the same bounded
aggregate query used the mapped administrative connection without selecting
prompts, document content, filenames, paths, or managed-store keys.

P2-03 must keep stable codes/classes, representation and MIME associations,
provider/model identities, capability associations, evidence state and dated
source, bound dimensions, locality/policy, effective dates, suitability,
health, selection/provenance contracts, and audit identity as separate
controlled concerns. Provider endpoint/request-field quirks and opaque native
metadata may remain bounded documented JSON only where they are not needed for
relational validation, policy, or routing. Current `properties.model_type`
defaulting to `TEXT` is not capability evidence.

Unresolved evidence remains: no P2-01 use case is validated; approved fixtures,
owners, measured expansion/output envelopes, and demonstrated
normalisation-insufficient outcomes are absent; sensitivity, consent,
locality, remote-processing, processor/backend, quality, cost, health, and
runtime-bound policy remain unresolved. `DOC_CLASS` remains content purpose,
all use cases remain `UNMAPPED` and remote-ineligible, direct Office-original
interpretation and video-temporal interpretation remain deferred, and all
negative P2-01 patterns remain rejected.

P2-02 added only the taxonomy document and structural documentation regression
coverage. No runtime or database capability was enabled. No database object,
row, property, configuration, privilege, provider adapter, plugin,
managed-store content, model, or deployed service was changed. P2-03 through
P2-10 remain not started.

**Final activity after resolution:** Return to
[@orac_document_materialisation_enhancements_plan](thread://019ff810-7695-7282-84e4-5fce86936a56)
and produce a decision-complete plan for P2-03, treating the approved capability
taxonomy as authoritative. Return it in the copy/paste-ready form required
above. Do not implement P2-03 during that planning activity.

### P2-03: Extend model and provider metadata

Design normalised capability and MIME associations around the existing
`llm_registry`, retaining JSON only for provider-specific details that do not
require relational validation or routing queries.

**P2-03 implemented and validated: 23-Aug-2026.**

The implementation record is
[`p2-03-controlled-model-provider-metadata.md`](p2-03-controlled-model-provider-metadata.md).
It adds controlled provider, capability, representation, MIME, provider-input,
model-evidence, and dimension-qualified limit structures around the existing
registry. The seed contains two reviewed adapters, 23 capability codes, 13
representations, three exact image MIME values, and six provider transport
declarations. No concrete-model capability was seeded or inferred from the
legacy effective `TEXT` default.

Concrete-model evidence is eligibility evidence for one configured immutable
model revision; it is not route authority. Route authority is a versioned
capability-requirement contract, while the exact provider/model/evidence chosen
for a real invocation is frozen later as runtime and audit evidence.

The existing `llm_registry_v` shape and Phase 1 prompt-only submission
behaviour remain unchanged. New read projections are exposed only through the
API and Code layers; runtime, APEX, and plugins received no new metadata DML or
read grant. Deployment and validation used the bounded `orac-db` fallback
because the local `orac-service` saved connection remained unavailable. No
model was queried, listed, loaded, downloaded, registered, probed, or invoked.

**Final activity after resolution:** Return to
[@orac_document_materialisation_enhancements_plan](thread://019ff810-7695-7282-84e4-5fce86936a56)
and produce a decision-complete plan for P2-04 against the resolved model and
provider metadata contract. Return it in the copy/paste-ready form required
above. Do not implement P2-04 during that planning activity.

### P2-04: Define media-type processing policy

Map media types to normalisation and materialisation strategies, not directly
to a single model. Support content-driven characteristic overrides.

**P2-04 policy planning completed: 23-Aug-2026.**

The approved planning record is
[`p2-04-media-type-processing-policy.md`](p2-04-media-type-processing-policy.md).
It defines provider/model-neutral media defaults, deterministic characteristic
overrides, fail-closed precedence, processing chains, representations,
dimension-qualified bounds, reason codes, and the P2-01 use-case mapping.
Optional specialist branches declare capability, representation/MIME,
behavioural-evidence, output, selection, and limit requirements rather than a
concrete model.
Existing Phase 1 text handling remains unchanged; direct Office-original and
video-temporal interpretation remain deferred. No processor, routing path,
attachment path, provider invocation, or policy table was implemented.

The standalone next-stage planning input is
[`p2-05-capability-aware-routing-and-fallback-plan.md`](p2-05-capability-aware-routing-and-fallback-plan.md).
P2-05 has not been implemented.

**Final activity after resolution:** Return to
[@orac_document_materialisation_enhancements_plan](thread://019ff810-7695-7282-84e4-5fce86936a56)
and produce a decision-complete plan for P2-05 using the approved media-type
processing policy. Return it in the copy/paste-ready form required above. Do not
implement P2-05 during that planning activity.

### P2-05: Define routing and fallback policy

Specify provider ordering, locality, classification, quality, cost,
availability, and fallback rules.

**P2-05 policy planning completed: 23-Aug-2026.**

The approved planning record is
[`p2-05-capability-aware-routing-and-fallback-policy.md`](p2-05-capability-aware-routing-and-fallback-policy.md).
It defines four controlled route kinds, ordered fail-closed eligibility gates,
stable reason codes, deterministic candidate ordering, independent
representation/MIME checks, explicit locality/classification and dated
observation contracts, and a non-widening fallback chain for every P2-04 media
family. Deterministic processor output remains authoritative and optional
specialist output remains attributed.

For `SPECIALIST_MODEL`, the controlled route identity is the immutable
capability-requirement identity. P2-05 evaluates configured concrete models as
candidates, excludes any without complete current evidence, orders the
remaining eligible candidates deterministically, and freezes the exact
provider/model revision, evidence, associations, observations, and effective
limits in one selection result. A different eligible model does not redefine
the route; it requires a new evaluation result.

Read-only validation reconfirmed two providers, 23 capabilities, 13
representations, three MIME values, six provider transport declarations, and
no concrete-model evidence or input limits. Image adapter support remains
`NOT_IMPLEMENTED`; no specialist or binary route is eligible. The existing
Phase 1 primary-text path remains an unchanged compatibility surface. No
routing engine, table, provider/model row, configuration, probe, attachment,
adapter, plugin path, or invocation was added.

The standalone next-stage planning input is
[`p2-06-secure-binary-materialisation-plan.md`](p2-06-secure-binary-materialisation-plan.md).
P2-06 has not been implemented.

**Final activity after resolution:** Return to
[@orac_document_materialisation_enhancements_plan](thread://019ff810-7695-7282-84e4-5fce86936a56)
and produce a decision-complete plan for P2-06, carrying forward the resolved
routing, fallback, locality, and classification decisions. Return it in the
copy/paste-ready form required above. Do not implement P2-06 during that
planning activity.

### P2-06: Implement secure binary materialisation

Create verified short-lived attachments from managed artefacts without exposing
content-store paths.

**P2-06 implemented and validated behind a disabled feature flag: 23-Aug-2026.**

The implementation record is
[`p2-06-secure-binary-materialisation-implementation-record.md`](p2-06-secure-binary-materialisation-implementation-record.md).
It delivers immutable P2-04/P2-05-bound request/result contracts,
descriptor-oriented managed-source revalidation, a bounded deterministic
processor seam, and private opaque single-use attachment handles with atomic
binding, expiry, cancellation, cleanup, startup recovery, and content-free
provenance. It reuses the existing authorised Core retrieval API and requires
no database persistence or privilege change.

P2-06 binds the exact P2-05 result without becoming model-selection authority.
For a specialist route the route fingerprint identifies the capability
requirement; any selected concrete-model evidence snapshot is per-evaluation
binding data. Changing that selection requires a new P2-05 result and a new
single-use attachment.

The shipped runtime remains disabled and has no eligible production processor
profile. Its default route revalidator defers every route, so P2-06 does not
manufacture binary or specialist eligibility. Positive tests use only isolated
synthetic fixtures. Phase 1 prompt-only behaviour remains unchanged, and no
provider/model was invoked, listed, loaded, pulled, downloaded, probed, or
registered.

The standalone P2-07 planning input is
[`p2-07-specialist-model-adapters-plan.md`](p2-07-specialist-model-adapters-plan.md).
P2-07 has not been implemented.

**Final activity after resolution:** Return to
[@orac_document_materialisation_enhancements_plan](thread://019ff810-7695-7282-84e4-5fce86936a56)
and produce a decision-complete plan for P2-07 against the implemented binary
materialisation interface and its verified limits. Return it in the
copy/paste-ready form required above. Do not implement P2-07 during that
planning activity.

### P2-07: Integrate specialist model adapters

Add adapters only for approved providers and proven use cases. Keep the primary
model responsible for final response generation unless a use case explicitly
requires otherwise.

Adapters are registered to exact provider/protocol/input-schema versions, not
to concrete models or route identities. P2-07 consumes the exact candidate
already selected by P2-05, revalidates that its P2-03 evidence still satisfies
the unchanged capability requirement, invokes only that identity, and records
the complete selection as runtime evidence. It cannot discover, rank,
substitute, or bless a model. Offline implementation and validation may use
synthetic model/evidence identities and a fake provider; a real provider call
remains disabled until at least one configured model is currently eligible.

**Final activity after resolution:** Return to
[@orac_document_materialisation_enhancements_plan](thread://019ff810-7695-7282-84e4-5fce86936a56)
and produce a standalone, decision-complete viability and implementation plan
for P2-08 using the accepted P2-03 through P2-07 authority and correlation
contracts. The plan must resolve or deliberately redesign around the P2-08
blockers below and must not assume that P2-09 or P2-10 will follow. Synthetic
identities and the fake provider may be used for planning and structural
validation; valid current runtime model evidence remains mandatory for any real
invocation. Return the P2-08 plan in the copy/paste-ready form required above.
Do not implement P2-08, P2-09, or P2-10 during that planning activity.

### P2-08: Decide viability of binary submission audit and observability

Record policy decisions, selected capability providers, hashes, payload shape,
timing, safe errors, and fallback outcomes.

**Status: viability and decision gate; no standalone implementation plan has
been accepted.**

P2-08 must first become a complete, internally consistent, and implementable
plan. Its blockers must be resolved or deliberately redesigned around before
implementation authorisation. It must demonstrate that audit lifecycle,
persistence, idempotency, terminal-state, retry, cancellation, attachment,
reconciliation, and provider-correlation contracts can be implemented without
violating the established P2-03 through P2-07 authority boundaries.

The P2-03 model-evidence catalogue remains eligibility evidence, not route or
audit authority. P2-05 remains the capability-based routing and exact
per-evaluation model-selection authority. P2-06 remains the source and
single-use attachment authority. P2-07 remains the exact adapter invocation and
attributed specialist-output authority. P2-08 may observe and correlate those
decisions and lifecycles, but must not rediscover, infer, widen, replace, or
retroactively bless them.

P2-08 planning and contract validation are not blocked by the absence of an
eligible production concrete model. Synthetic provider, model, evidence,
capability-requirement, route-selection, adapter, attachment, attempt, and
outcome identities plus the fake provider are sufficient to prove cardinality,
lineage, redaction, timing, fallback, and terminal-state contracts. Real
invocation audit must nevertheless record the exact provider, `llm_id`,
immutable model revision/digest, model-evidence and capability associations,
route requirement, selected limits, adapter/protocol, and fallback position
actually used. Synthetic evidence can never authorise a real invocation.

#### P2-08 blocker classification

1. **Genuine prerequisites before P2-08 implementation**

   - The P2-03 through P2-07 authority, identity, correlation, and redaction
     contracts consumed by P2-08 must be accepted and stable enough that P2-08
     cannot become an alternate route, model-evidence, attachment, adapter, or
     fallback authority.
   - The standalone P2-08 plan must define one authoritative audit lifecycle
     and ownership model for request, route evaluation, attachment, provider
     attempt, retry, cancellation, late result, terminal outcome, cleanup, and
     reconciliation events.
   - Persistence authority, least-privilege access, retention, redaction,
     immutable identities, cardinality, idempotency keys, terminal-state
     transitions, transaction boundaries, rollback, and bounded reconciliation
     must be decision-complete before database implementation is proposed.
   - The plan must prove that no database transaction spans long filesystem,
     attachment, processor, or provider work and that repeated delivery,
     cancellation, timeout, crash recovery, and late provider results cannot
     create contradictory terminal outcomes.

2. **Planning dependencies that can be represented conditionally**

   - Provider-specific correlation IDs, timing, usage, retention, and error
     fields may be expressed as controlled optional capabilities with explicit
     `AVAILABLE`, `UNAVAILABLE`, and `NOT_APPLICABLE` semantics. Their absence
     must not be filled by inference.
   - The plan may describe conditional persistence alternatives depending on
     whether existing retrieval audit structures can preserve the required
     cardinality and lifecycle without boundary widening. No new database
     object is assumed until that comparison is resolved.
   - Synthetic provider/model/evidence, route, attachment, adapter, attempt,
     retry, cancellation, reconciliation, and outcome identities plus the fake
     provider are sufficient for planning, schema-shape tests, state-machine
     tests, and structural validation.
   - Real-provider correlation and operational acceptance remain conditional on
     valid current P2-03 model evidence, an eligible P2-05 result, an approved
     P2-07 adapter, and separately authorised invocation. Those conditions do
     not block P2-08 design.

3. **Unnecessary coupling to remove**

   - P2-08 design must not require a blessed, production-eligible, locally
     installed, or remotely available concrete model.
   - P2-08 design must not require model listing, loading, pulling, download,
     probing, registration, inference, real provider state, or real document
     content.
   - P2-08 must not be designed around anticipated P2-09 administration screens
     or P2-10 end-to-end tests. Those placeholders cannot define P2-08 storage,
     event, privilege, or lifecycle contracts.
   - Provider identity must not replace capability-based routing, and an audit
     row must never be treated as route eligibility, model evidence, attachment
     authority, or permission to retry.

4. **Evidence that P2-08 should be decomposed if a clean single-phase design
   cannot be proved**

   - If immutable audit persistence and the runtime terminal-state machine
     cannot share one clear ownership and idempotency contract, separate the
     audit event/state contract from its database persistence and recovery
     implementation.
   - If provider correlation, timing, usage, and retention vary too widely for
     one stable bounded contract, separate provider-correlation observability
     from the core content-free lifecycle audit.
   - If attachment cleanup/reconciliation and provider-attempt reconciliation
     require different recovery authorities, keep those recovery slices
     separate and correlate them by immutable identities rather than creating a
     cross-boundary repair service.
   - If a proposed complete submission audit requires storing content,
     credentials, provider payloads/replies, paths, managed keys, or inferred
     model evidence, reduce scope, split the work, or reject that design.

#### P2-08 decision outcomes

The standalone P2-08 plan must end in one explicit outcome:

- `ACCEPT`: the design is decision-complete and implementable without widening
  P2-03 through P2-07 authority;
- `REVISE`: specified blockers require another planning pass;
- `REDUCE_SCOPE`: only a narrower audit lifecycle is coherent;
- `DECOMPOSE`: two or more smaller independently accepted phases are required;
  or
- `REJECT`: the proposed audit/observability architecture cannot be implemented
  safely within the established boundaries.

Only `ACCEPT`, followed by separately authorised implementation and acceptance
of P2-08, permits reconsideration of downstream placeholders. A `DECOMPOSE`
outcome requires each replacement phase to be implemented and accepted before
that reconsideration. `REVISE`, `REDUCE_SCOPE`, or `REJECT` does not implicitly
authorise P2-09 or P2-10.

### P2-09: Add administration and validation tooling

Provide maintainable configuration and capability tests. Do not allow an
administrator to declare unsupported capabilities without a validation or
health signal.

**Status: contingent placeholder only.**

P2-09 is neither assumed nor authorised. Do not create a detailed P2-09 plan
until P2-08, or every accepted replacement phase from a P2-08 decomposition,
has been implemented and accepted. At that point the master plan must first
decide whether administration or validation tooling is still necessary,
whether it belongs in P2-09, and whether it can consume the accepted audit
contracts without becoming capability, model-evidence, routing, or invocation
authority. If P2-08 is revised, reduced, deferred, or rejected, retain,
rescope, defer, or remove this placeholder accordingly.

### P2-10: Add end-to-end multimodal security tests

Test unauthorised access, remote-processing restrictions, classification
ceilings, corrupt files, MIME spoofing, oversized payloads, unsupported
modalities, provider failure, and safe fallback.

**Status: contingent placeholder only.**

P2-10 is neither assumed nor authorised. Do not create a detailed P2-10 plan
until P2-08, or every accepted replacement phase from a P2-08 decomposition,
has been implemented and accepted and the continued need and scope of P2-09 has
been decided. Existing component-level security tests remain mandatory and
must not be deferred to P2-10. If P2-08 does not establish a coherent accepted
audit lifecycle, this end-to-end phase must be rescoped, deferred, or removed
rather than forcing tests around unresolved architecture.

## Cross-cutting requirements

### Security

- Treat all document and derivative content as untrusted.
- Preserve current RAG usage privilege and scope checks.
- Fail closed when authorisation, classification, storage verification, or
  provider policy cannot be resolved.
- Do not let prompts override retrieval or routing policy.
- Do not expose absolute storage paths, credentials, raw stack traces, or
  unrestricted converter output.
- Validate MIME type, signature, hash, size, and managed-root containment at
  appropriate boundaries.

### Provenance

- Preserve raw source hash, normalised artefact hash, extractor identity,
  extractor version, chunker identity, embedding model identity, and model
  submission identity.
- Record which artefacts or logical sections were supplied for a response.
- Do not duplicate whole document content in response provenance.

### Performance and limits

- Use bounded reads and streams where possible.
- Estimate tokens before sending complete normalised content.
- Avoid loading very large CSV payloads into memory without a documented bound.
- Support selection and partitioning for large artefact packages.
- Do not make ingestion completion depend on future binary model availability.

### Compatibility

- Preserve current source identity and document revision semantics.
- Preserve searchable completion invariants.
- Avoid breaking existing Drop Box jobs and Core request correlation.
- Provide a controlled transition for existing extraction CLOBs.
- Keep Phase 2 metadata inactive or absent until the future feature is enabled.

### Testing

The final Codex plan must include:

- DDL and migration tests;
- API authorisation tests;
- content-store unit and integration tests;
- hash, corruption, traversal, and symlink tests;
- idempotency and concurrency tests;
- ingestion retry and orphan tests;
- retrieval and materialisation limit tests;
- prompt-boundary tests;
- backward-compatibility tests;
- documentation validation against implemented configuration and schema.

## Explicit non-goals for Phase 1

Phase 1 must not silently expand into:

- arbitrary binary upload to any model;
- a general-purpose model marketplace;
- automatic installation of converters or system packages;
- unrestricted filesystem tools for the LLM;
- replacement of deterministic SQL or Python calculation with model reasoning;
- full spreadsheet ingestion unless separately approved;
- OCR, PDF, presentation, audio, or video ingestion unless already part of an
  independently approved scope;
- direct plugin DML against Core knowledge tables;
- deletion or mutation of immutable source or derivative payloads;
- unbounded backfill during deployment.

## Questions Codex must answer in plan mode

Codex must inspect the repository and answer these questions explicitly in its
plan:

1. Where is the current managed content store implemented and configured?
2. Is `knowledge_document_versions.content_uri` always a Core-managed,
   hash-sharded raw object locator?
3. Are raw originals verified on both write and read?
4. What legacy or exceptional `content_uri` values exist or are supported?
5. Does the current code centralise shard path construction?
6. Should normalised artefacts extend `knowledge_extractions`, use a general
   artefact table, or use a package/member design?
7. How should authority be divided between extraction CLOB content and the
   disk-resident normalised artefact?
8. How can existing extraction CLOBs be migrated or backfilled safely?
9. Which schema, package, view, grant, runtime, plugin bridge, and APEX files
   require change?
10. Which existing APIs are safe extension points and which boundaries must not
    be crossed?
11. How will RAG usage privileges apply to complete-document and selected-table
    materialisation?
12. What token and byte limits already exist and where should new limits live?
13. How will missing, corrupt, orphaned, or mismatched disk artefacts be
    detected and reported?
14. What is the minimum Phase 1 slice that provides real LLM access to complete
    normalised content without building Phase 2 prematurely?
15. Which Phase 1 design decisions intentionally prepare for, but do not
    implement, Phase 2?

## Required form of the Codex plan

Codex should return a plan containing:

1. **Repository findings** with exact file and object references.
2. **Current-state data flow** from Drop Box discovery to retrieval.
3. **Schema gap analysis** grounded in the checked-out DDL and migrations.
4. **Chosen Phase 1 design**, including rejected alternatives and rationale.
5. **Detailed implementation sequence** with dependencies and migration order.
6. **Exact affected components** across schema, APIs, Python runtime, plugin
   bridge, model adapter, configuration, APEX, tests, and documentation.
7. **Backfill and compatibility strategy**.
8. **Security and authorisation analysis**.
9. **Failure, retry, orphan, and reconciliation behaviour**.
10. **Test plan and acceptance evidence**.
11. **Phase 2 design record**, clearly marked deferred and excluded from
    near-term implementation.
12. **Open decisions** that genuinely require product or architectural input.

Codex must challenge assumptions in this document when repository evidence
contradicts them. It must not merely restate the backlog.

## Suggested Codex plan-mode prompt

```text
Read the attached Orac Document Materialisation and Binary Model Routing
Enhancements planning brief in full.

Operate in plan mode only. Do not modify files, create commits, or implement
changes.

Inspect the current repository and all applicable AGENTS.md,
AGENT_CONTEXT.md, guardrails, schema DDL, Liquibase controllers and migrations,
Core capture and ingestion services, Drop Box plugin code and documentation,
knowledge APIs and views, retrieval and dialogue routing code, model adapters,
configuration, APEX exports, and tests.

Produce an evidence-based execution plan for Phase 1 only. Include a grounded
check of the current database schema and managed content-store implementation.
Prove how raw originals are currently hash-sharded and how content_uri is used.
Identify the current absence or presence of durable disk pointers for
normalised artefacts.

Compare the normalised artefact schema alternatives in the brief and select the
least disruptive design that supports both single Markdown outputs and future
multi-file spreadsheet outputs such as a Markdown manifest plus CSV tables.
Explain rejected alternatives.

Your plan must name exact files, schema objects, APIs, tests, migration order,
compatibility work, security checks, failure handling, and acceptance evidence.
Preserve Core ownership, plugin boundaries, RAG usage authorisation,
content-addressed immutable storage, and existing ingestion completion
invariants.

Treat Phase 2 as a deferred architecture record only. Document any Phase 1
choices needed to avoid blocking future binary submission and capability-aware
model routing, but do not include Phase 2 implementation in the near-term plan.

Call out every unresolved assumption or product decision. Do not paper over
repository contradictions. Do not create a commit.
```

## Planning review checklist

Use this checklist when scrutinising each Codex plan revision:

- Does the plan prove the current raw storage behaviour from code?
- Does it distinguish raw document versions from normalised extraction
  artefacts?
- Does it support multiple derivative files without forcing premature
  spreadsheet implementation?
- Does it avoid absolute host paths as durable identity?
- Does it preserve hash-sharding and immutable content?
- Does it define authority between database CLOBs and disk artefacts?
- Does it include a realistic migration or backfill path?
- Does it preserve schema and plugin boundaries?
- Does it enforce RAG privileges for broader materialisation?
- Does it use progressive disclosure and context limits?
- Does it keep raw binary submission out of Phase 1?
- Does it avoid direct MIME-to-model coupling in Phase 2?
- Does it include corruption, orphan, retry, concurrency, and security tests?
- Does it name exact files and dependencies rather than offering thematic work
  packages?
- Does it state what will not be changed?

## Source material supplied for this planning brief

This brief was prepared from:

- the supplied current Core schema archive;
- the supplied Drop Box plugin documentation archive;
- the supplied `document-ingestion.md` document;
- the preceding architecture discussion concerning normalised Markdown and CSV
  materialisation, raw document retrieval, and future capability-aware binary
  model routing.

Codex must treat the checked-out repository as the final authority if it has
advanced beyond the supplied snapshots.
