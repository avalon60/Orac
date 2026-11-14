# Document Ingestion

Orac document ingestion is a Core-owned knowledge lifecycle with source
adapters at its boundary. The bundled Drop Box plugin is the first implemented
adapter: it discovers local files and produces canonical Markdown, while Core
owns durable source storage, knowledge records, chunking, embeddings, tags,
searchability, retrieval, and grounding provenance.

For Drop Box installation and day-to-day operation, see the
[Drop Box operator guide](../plugins/drop_box/docs/drop-box.md). Maintainers
should also read the
[Drop Box data lifecycle](../plugins/drop_box/docs/drop-box-data-lifecycle.md).

## Responsibility Boundary

| Owner | Responsibilities |
| --- | --- |
| Drop Box plugin | Filesystem discovery, stability checks, source hashing, format and archive validation, native text normalisation, allowlisted Pandoc conversion and Poppler PDF extraction, plugin-owned job/audit state, and submission to the Core capture service. |
| Orac Core capture | Revalidate the source identity and canonical Markdown, persist both immutable representations in the Core-managed content-addressed store, register the complete normalised output set, resolve the canonical scope, and create the transactional knowledge lineage and ingestion request. |
| Orac Core worker | Claim queued requests, verify registered managed artefacts, create source-specific Markdown or CSV chunk sets, create embeddings, enforce completion invariants, and record bounded request events and failure state. |
| Orac Core retrieval | Authorise an authenticated principal for one active canonical scope, select searchable chunks, construct bounded untrusted evidence, and retain response provenance. |

Plugins do not write to protected Core tables. Drop Box owns its private
`ORAC_DROPBOX` schema and reaches Core through approved bridge and application
APIs. Core remains responsible for orchestration, persistence, authorisation,
and the model-facing context boundary.

## End-to-End Flow

1. The Drop Box scanner loads enabled locations from its runtime view.
2. It filters hidden, ignored, symlinked, disallowed, oversized, or unstable
   files before hashing.
3. A stable observation creates one durable Drop Box job. The job snapshots its
   target scope, classification tags, and ingestion notes.
4. Drop Box validates the source format and produces canonical
   GitHub-flavoured Markdown. Markdown and plain text are normalised natively;
   DOCX, HTML, ODT, RTF, and EPUB use the fixed Pandoc recipe; text-based PDFs use Poppler extraction with page markers.
5. `KnowledgeManagedFileCaptureService` revalidates the original file, hashes,
   canonical Markdown, MIME values, extractor identity, bounded extraction
   metadata, classification tags, and ingestion notes.
6. Core copies the original and canonical Markdown into the managed content
   store and calls `orac_code.knowledge_ingestion_api.submit_managed_file` with
   the complete normalised output-set envelope.
7. The database creates or reuses the source object and document, creates the
   appropriate document version and extraction, atomically registers its
   immutable artefact members, persists relational tags, and queues an
   ingestion request.
8. The Core `knowledge_ingestion` worker claims the request, verifies every
   chunkable managed member, creates one artefact-owned chunk set per PRIMARY,
   MANIFEST, or TABLE member, embeds every searchable chunk with the immutable
   knowledge profile, stores it as native `VECTOR(768,FLOAT32)`, and marks the
   request complete only when output-set and embedding invariants pass. Legacy
   extraction CLOBs may remain content sources; legacy JSON/hash vectors are
   not production semantic storage.
9. Scope-authorised dialogue retrieval may use the completed current chunks
   when `[knowledge.dialogue].enabled` is enabled.

Ingestion and dialogue retrieval are separate controls. A document can be
ingested while dialogue retrieval is explicitly disabled, and a RAG usage
grant does not authorise document submission.

The version-two Markdown chunker accounts with a conservative UTF-8-byte upper
bound rather than whitespace words. It derives a hard content ceiling from the
resolved embedding model context, the configured safety margin, Nomic's
document prefix, and special-token allowance. Long table-of-contents lines,
URLs, paths, punctuation-heavy text, and low-whitespace content are therefore
split before embedding. Ollama truncation stays disabled.

## Source Identity and Revisions

Drop Box derives its readable source key from:

```text
<location_code>:<canonical-relative-posix-path>
```

Core stores an opaque source reference derived from that key:

```text
drop_box:source:<sha256(source_key)>
```

Absolute host paths are not part of the durable source identity. The
consequences are:

- changed content at the same location code and relative path creates a new
  version of the same document;
- a rename or relative-path move creates a new source and document identity;
- moving a location root while preserving its code and relative paths
  preserves identity;
- changing the location code creates new identities.

Legacy `drop_box:drop_job:<id>` identities are re-keyed only when Core can prove
one unambiguous match without colliding with an existing stable reference.

## Managed Content and Database Lineage

The `[knowledge].managed_root` directory is the Core-owned content-addressed
pool for raw originals and normalised artefacts. Database references
use the root-independent logical key:

```text
sha256:<full-sha256>
```

Core alone derives the internal physical layout:

```text
sha256/<first-two>/<next-two>/<full-sha256>
```

Existing legacy database locators in that physical form remain readable.
New registrations use only logical keys, and plugins never receive or resolve
physical managed-object paths.

`KnowledgeManagedStore.put_stream(...)` is the primary write boundary.
Raw capture supplies the hash and byte size already established by the source
adapter; future Core-generated artefacts may let the store calculate and return
that identity while streaming. `put_file(...)` and `put_bytes(...)` are
convenience delegates, not separate storage implementations. Promotion uses a
same-filesystem hard link as an atomic no-replace operation and reports
`installed` or `reused`. A reused object is accepted only after its immutable
hash and byte size have been verified.

`open_verified(...)` resolves logical or exact legacy keys beneath the fixed
root using descriptor-relative, no-follow operations. It opens the payload
once, verifies that descriptor is a regular file with safe permissions, checks
its registered size and hash through that descriptor, rewinds it, and returns
a context-managed binary stream over the same descriptor.

The managed store authorises and protects destination storage. Drop Box still
owns source-location authorisation and provenance: Core checks lexical
containment beneath the configured Drop Box root, opens every source path
component without following symlinks, requires a regular-file descriptor, and
checks size and descriptor stability before database registration.

Runtime code has one physical-path authority:
`src/orac_core/knowledge/managed_store.py`. Capture, worker, plugin, and
database code may handle logical keys but must not construct shard paths.
Permitted physical inspection is limited to managed-store tests, the P1-05
controlled locator migration, and the implemented P1-09 read-only inventory
and reconciliation service. Those tools consume the store's canonical layout
rules rather than establishing an independent runtime resolver.

The database owns the relational lineage:

```text
knowledge scope
  -> source object
  -> document
  -> document version
  -> extraction
  -> normalised artefact
  -> artefact-owned chunk set
  -> chunk
  -> immutable embedding profile
  -> native chunk vector embedding
```

The ingestion request and its events record the asynchronous lifecycle. Core
stores canonical Markdown as an immutable managed PRIMARY artefact during
submission. The extraction CLOB remains a compatibility projection whose
canonical UTF-8 hash must agree with the PRIMARY or spreadsheet MANIFEST. The
worker chunks verified managed bytes and records the precise source artefact on
each new chunk set. The raw managed object remains the verified original
source, not a plugin-owned knowledge store.

SINGLE output sets contain exactly one Markdown PRIMARY plus optional bounded
METADATA. SPREADSHEET output sets contain exactly one Markdown MANIFEST and one
or more independently chunkable CSV TABLE members with bounded sheet, table,
cell-range, header-row, and hidden-sheet metadata. A set is registered
atomically and idempotently; incomplete or inconsistent sets cannot become
searchable or complete.

### Lifecycle authority

| Lifecycle object | Authority and compatibility boundary |
| --- | --- |
| Raw original | The immutable document-version hash, byte size, MIME type, and logical storage key identify the source bytes accepted by Core. Drop Box authorises the source location but does not own the durable copy. |
| Extraction CLOB | A compatibility projection and the legacy source for extractions that have no artefacts. For new sets, its canonical UTF-8 identity must match the PRIMARY or MANIFEST member. |
| Normalised output set | The immutable managed PRIMARY, MANIFEST, TABLE, and optional METADATA members are authoritative for new worker, retrieval, and materialisation reads. The database owns membership, order, completeness, and extraction lineage. |
| Chunk set and chunks | Each new chunk set belongs to one exact chunkable artefact in the same extraction. A null source remains valid only for legacy CLOB-backed lineage. |
| Retrieval and materialisation | Core authorises a principal and canonical scope, resolves database identities, verifies registered content, and emits bounded untrusted evidence. Callers never supply paths or storage keys. |
| Reconciliation | The read-only operator service compares bounded Oracle snapshots with a non-following physical inventory. It reports divergence but has no authority to repair or mutate either side. |

Raw document-version identity and durable provenance are immutable during
ordinary runtime operation: document-version and document identifiers, source
object identifier, content hash, storage key, MIME type, original filename,
byte size, source modification timestamp, source format, creator, and creation
timestamp. The database trigger rejects updates to those columns and rejects
document-version deletion. Audit update fields and row version remain the only
mutable document-version fields. P1-05 is the sole planned exception for a
controlled legacy raw-locator migration.

Existing canonical CLOB-only extractions can be migrated without changing
chunk or embedding identities. The dry-run-first
[`orac-knowledge` maintenance command](knowledge-maintenance.md) runs a
read-only preflight, writes or reuses the CLOB bytes as a PRIMARY artefact,
and attaches existing legacy chunk sets in the same per-extraction database
transaction. Liquibase deployment installs the migration API but never runs
this operational backfill automatically.

Core schema ownership follows the normal Orac layers:

- `ORAC_CORE` owns knowledge tables, constraints, indexes, tags, and seed data.
- `ORAC_API` exposes controlled table APIs and pass-through views.
- `ORAC_CODE` owns `knowledge_ingestion_api`, scope APIs, business views, and
  the approved runtime/APEX surfaces.
- `ORAC` is the least-privilege Python runtime schema.
- `ORAC_APX_PUB` is the least-privilege APEX parsing schema.
- `ORAC_PLUGIN` is the controlled plugin bridge.

## Request Lifecycle and Failure Behaviour

Core request statuses are `QUEUED`, `PROCESSING`, `RETRY_WAIT`, `COMPLETED`,
and `FAILED`.

- A worker claim has a bounded lease. An expired processing lease may be
  reclaimed.
- Stage changes remain within `PROCESSING` while chunking and embedding run.
- A retryable worker error enters `RETRY_WAIT`; retry exhaustion enters
  `FAILED`.
- Completion is rejected unless the request has searchable chunks and every
  searchable chunk has an embedding.
- Only the newest chunk-set generation for each extraction/source artefact is
  current. Historical chunk sets and vectors remain durable lineage but are
  excluded from completion coverage and searchable projections.
- `EMBEDDING_INPUT_CONTEXT_EXCEEDED` is a permanent, content-free diagnostic
  containing only chunk position, conservative estimate, limits, and profile
  identity; document text is never included.
- A malformed or unsafe key, symlink, non-regular file, missing object,
  permission defect, or hash/size mismatch is a permanent request failure.
- A genuinely transient store I/O error maps to `MANAGED_STORE_UNAVAILABLE`
  and may enter `RETRY_WAIT`.
- Root identity, permission, filesystem, or hard-link capability failures are
  service configuration failures. Startup fails closed before work is claimed;
  Drop Box does not retry unsupported promotion separately for every document.

Capture validates before handing authority to the database. A validation or
idempotency conflict fails the Drop Box handoff. A transient Core/database
failure leaves the plugin job queued for a later attempt. If source promotion
succeeds but database registration fails, the content-addressed file may remain
as an unregistered object; a retry verifies and safely reuses the same hash.
Reconciliation treats a recent object as an incomplete concurrent-promotion
case and only calls a stable, sufficiently old object a confirmed orphan.

An interrupted promotion can leave either no destination and a removable
store-owned temporary file, or a complete durable destination that a retry can
reuse. Stale temporary files, confirmed orphans, missing objects, and corrupt
objects are diagnostics, not automatic repair instructions. Operators may use
the [read-only reconciliation command](knowledge-maintenance.md#read-only-operational-reconciliation)
to classify them, but cleanup, registration, quarantine, deletion, locator
rewriting, and content recovery require a separately authorised future
workflow.

The Drop Box-specific states and conversion retry rules are documented in the
[data lifecycle](../plugins/drop_box/docs/drop-box-data-lifecycle.md).

## Classification Tags and Ingestion Notes

Core owns document classifications as reference values in the fixed
`DOC_CLASS` domain. Drop Box requires one to ten active, distinct uppercase
reference-value codes and snapshots the selection with each job. Core validates
the snapshot again and persists the composite domain/reference keys on the
document version.

The seeded tags are:

- `RAW_REFERENCE`
- `CONCISE_KNOWLEDGE_NOTE`
- `IMPLEMENTATION_DECISION_RECORD`
- `TECHNICAL_MANUAL`
- `TROUBLESHOOTING_NOTE`
- `AUTOMATION_RULE_NOTE`

Tags describe content. They do not select converters, alter chunking or
embeddings, influence ranking or authorisation, enter privileged prompts, or
change routing.

Ingestion notes are bounded, untrusted provenance. They are never executed and
are not model instructions. Processing profiles remain operational metadata;
they are not converted into document classifications.

There is currently no classification-tag maintenance page in Core App 1042.
Drop Box App 10020 selects active Core-owned tags through
`orac_code.knowledge_tag_lov_v`.

## Runtime Configuration

The full key-by-key reference is in
[Configuration Reference](configuration.md#knowledge).

### `[knowledge]`

| Setting | Purpose |
| --- | --- |
| `enabled` | Registers the synthetic `orac_core:knowledge_ingestion` service when true. It does not enable dialogue retrieval. |
| `managed_root` | Core-owned root for the shared raw/normalised content-addressed pool and store-owned temporary files. |
| `request_lease_seconds` | Lease duration for a claimed ingestion request. |
| `batch_size` | Maximum requests handled during one worker tick. |
| `chunk_size_tokens` | Target word-window size for structure-aware Markdown chunks. |
| `chunk_overlap_tokens` | Bounded overlap between adjacent chunks. |

Production embedding settings live under `[embedding.knowledge]`: provider,
endpoint, model tag and digest, fixed 768 dimensions, immutable profile and
policy versions, Nomic document/query prefixes, `truncate=false`, and the
profile-specific semantic threshold.

The built-in worker runs on start and then every 30 seconds with bounded jitter.
Setting `enabled = false` prevents service registration after the next runtime
refresh or restart; it does not delete existing knowledge records.

### `[knowledge.dialogue]`

This section controls dialogue retrieval, not ingestion. The shipped
configuration enables it; an explicit `enabled = false` disables it. Other
settings include canonical scope aliases, registry cache lifetime, the bounded
semantic/lexical candidate union, selected-chunk limits, context budgets, and
the lexical-branch threshold.

Every retrieval requires a current Oracle `USE` privilege. The former
`allow_all_scopes` bypass is retired and rejected at startup if configured.

Normalised document, artefact, member, table, section, and chunk retrieval is
described in [Authorised Knowledge Retrieval](knowledge-retrieval.md). Raw
binary submission remains outside this interface.

See [Dialogue Routing](dialogue-routing.md) for the matching and grounding
contract.

## Shipped Orac Documentation Location

The Core database install seeds the active `PROJECT:ORAC_CORE` scope. The Drop
Box plugin install separately seeds the enabled `ORAC_DOCS` adapter with these
defaults:

- source path `${ORAC_HOME}/docs`, resolved by the scanner against its runtime
  project home;
- recursive Markdown-only scanning;
- target `PROJECT:ORAC_CORE` and classification code `RAW_REFERENCE`;
- exclusions for `pending_work/**`, `backlog/**`, hidden files, and common
  temporary or partial-file patterns;
- no source-file movement, deletion, or quarantine.

The location is operational configuration, not a dialogue alias or a user
privilege. Dialogue retrieval still requires an active `USE` grant for
`PROJECT:ORAC_CORE`.

## Core APEX Configuration

All three applications use workspace `ORAC` and parsing schema
`ORAC_APX_PUB`. Core administration is App 1042, Plugin Control is App 1043,
and Drop Box Admin is plugin-owned App 10020.

### App 1042: Projects, Pages 37 and 38

The install seeds `ORAC_CORE`; create another active project before selecting
that additional project as a Drop Box target.

- Page 37 reports registered projects and opens the create/edit drawer.
- Page 38 maintains project code, display name, description, and active state
  through `orac_code.project_registry_api`.
- Project codes are uppercase identifiers containing letters, digits, and
  underscores. A code becomes immutable after creation.
- Deactivation preserves the canonical scope, corpus, configuration, and
  history but makes the target unavailable for new supported operations.
- Hard deletion is not an administrator workflow.

Plugin scopes are derived from the installed plugin registry and must be
enabled and runtime-eligible. They are not created from a Drop Box location.
An installed plugin's APEX application can submit an authorised asynchronous
search against its own plugin scope through the
[Plugin APEX Knowledge Search](plugin-apex-knowledge-search.md) API. The
signed-in APEX user still needs a current `USE` grant on that scope.

### App 1042: RAG Usage Privileges, Pages 39 and 40

- Page 39 reports active, scheduled, expired, and revoked `USE` privilege
  history for canonical project and plugin scopes.
- Page 39 displays Scope Type and Target separately and passes only the
  selected numeric privilege ID to Page 40. Project and Plugin filters are
  mutually exclusive and follow Scope Type.
- In new-grant mode, Page 40 keeps scope type separate from its conditional
  Project or Plugin selector. The selected target is a `knowledge_scope_id`;
  no `TYPE:key` value is concatenated or split.
- In existing-entry mode, principal, scope type, target, effective timestamp,
  and expiry timestamp are read-only. Revoke uses the selected row ID and
  protected row version to soft-delete that exact stored-active entry. It sets
  `active_yn = 'N'`, records revocation metadata, and retains the row as
  view-only history. Re-granting the relationship creates a new active row.
- Both pages use `orac_code.rag_usage_privilege_api`; they do not perform direct
  table DML.

These grants control whether an authenticated user may retrieve from an
ingested scope during dialogue. They do not create a scope, enable a Drop Box
location, or authorise document ingestion. See
[RAG Usage Privileges](rag-usage-privileges.md).

### App 1043: Plugin Control

- Page 1, **Plugin Operations**, reports managed service state. Use the
  `drop_box` / `scanner` row to choose `auto`, `manual`, or `disabled`. The
  synthetic `orac_core` / `knowledge_ingestion` worker is present only when
  `[knowledge].enabled` allows it to be registered.
- Page 2, **Plugin Navigation**, launches enabled installed plugin
  applications, including Drop Box Admin.
- Pages 3 and 4, **Manage Plugin Apps** and **Plugin App**, report and change
  plugin APEX-app enablement. Enabling an app row is not the same as installing
  the plugin or starting its scanner.

App 1043 does not edit drop locations, classification tags, Core chunking
settings, or RAG usage privileges.

## Security and Provenance

- Source documents, converter output, tags, and ingestion notes are untrusted
  data, not instructions.
- The original file must remain under its configured location root and match
  the declared size and SHA-256 before Core accepts it.
- Plugin-to-Core access uses approved APIs rather than direct protected-table
  access or cross-schema foreign keys.
- APEX shows bounded administrator-safe error summaries. Raw converter output,
  stack traces, credentials, unrestricted event payloads, and ingestion notes
  are not exposed.
- Retrieval requires an authenticated active principal and an active eligible
  canonical scope. Selected chunks are injected only as bounded untrusted
  evidence.
- Provenance records identifiers, hashes, model and converter identities,
  counts, safe reason codes, and timing without persisting whole documents in
  assistant metadata.

## Unsupported or Deferred Capabilities

The current ingestion path does not provide:

- OCR for scanned or image-only PDFs;
- spreadsheet or presentation conversion;
- remote acquisition, email ingestion, or embedded-media extraction;
- model-generated document transformation;
- automatic activation of a changed profile without complete native-vector
  validation;
- file movement, deletion, or quarantine after processing;
- an unreviewed manual terminal-job requeue action;
- an Oracle vector index for the initial small corpus. Exact native vector
  distance is used until measured corpus/latency growth justifies an index.

Phase 2 raw-binary submission and model-capability routing are also deferred.
The current model path accepts only authorised, bounded normalised text
evidence; neither a raw document locator nor a provider's text-evidence
eligibility grants binary attachment capability.
