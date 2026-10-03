# Drop Box Data Lifecycle

Drop Box is a source adapter for Orac's Core knowledge lifecycle. It owns local
file discovery, source validation, canonical Markdown production, and
plugin-private job history. It does not own the Core corpus, chunking,
embeddings, retrieval policy, or grounding context.

For installation and APEX configuration, see the
[Drop Box operator guide](drop-box.md). The Core lifecycle and configuration
contract is in [Document Ingestion](../../../docs/document-ingestion.md).

## Ownership and Access

| Component | Owned state or responsibility |
| --- | --- |
| `ORAC_DROPBOX` | Drop locations, compatibility profiles, jobs, retry metadata, and job events. |
| Drop Box scanner | Filesystem observations, in-process stability memory, SHA-256 hashing, and durable enqueue. |
| Drop Box converter | Source-format validation, native canonicalisation, controlled Pandoc invocation, and bounded extraction provenance. |
| `ORAC_PLUGIN` bridge | Approved Core validation interfaces exposed to plugin-owned schemas. |
| Orac Core capture | Source revalidation, content-addressed storage of the raw original and canonical Markdown, atomic normalised output-set registration, scope resolution, transactional document lineage, tags, and ingestion request creation. |
| Orac Core worker | Leased request processing, verification and independent chunking of PRIMARY, MANIFEST, or TABLE members, embeddings, completion, retry, and Core events. |

The expected grant direction is:

```text
ORAC_DROPBOX -> ORAC_PLUGIN (approved validation interfaces only)
host-managed Drop Box service -> Core capture service -> ORAC_CODE
ORAC_CODE    -> ORAC_APX_PUB
ORAC_DROPBOX -> ORAC_APX_PUB (approved admin views and package only)
```

There is deliberately no `ORAC_DROPBOX -> ORAC_CORE` foreign key. Supported
location writes validate type/key scope references through
`orac_plugin.knowledge_scope_validation_api`. Direct privileged DML in the
plugin owner remains an unsupported residual risk rather than a reason to
bypass the schema boundary.

The resolved `target_knowledge_scope_id` is stored on each location and copied
onto jobs. Enqueue checks that exact ID through the bridge; Core ingestion
checks the same ID and rejects a retired, ineligible or successor target.
The job snapshot is immutable. An ordinary location edit preserves its ID;
an explicit **Use Current Installation** save resolves a fresh target for future
jobs. No ordinary ingestion path reparents an existing source to another scope.

The plugin manifest declares the scope and tag validation bridge dependencies.
During plugin install or reconcile, the host provisions `ORAC_DROPBOX`, checks
that both `ORAC_PLUGIN` packages are valid, grants only `EXECUTE` to
`ORAC_DROPBOX`, and then runs the plugin changelog. These grants are not part of
the core changelog, so core deployment remains valid when Drop Box is absent.
The host-managed scanner invokes the Core capture service in-process; its Core
database work uses the `ORAC` runtime repository. Neither `ORAC_PLUGIN` nor
`ORAC_DROPBOX` receives execution on the broad ingestion package.

## Location and Job Snapshots

An enabled location defines:

- stable location code and display name;
- runtime-visible source root;
- project or plugin target scope;
- one to ten classification tags;
- provenance-only ingestion notes;
- extension, recursion, ignore, size, and stability rules;
- stored future post-processing paths.

At enqueue, the database copies effective scope, tags, the compatibility
primary profile, legacy profile instruction, and location-specific ingestion
notes onto the job. Later location edits do not rewrite historical job
snapshots.

The legacy `drop_processing_profile` table and related columns remain because
older jobs and schema relationships depend on them. Processing profiles and
classifications are configured independently: profiles preserve compatibility
metadata, while classifications are uppercase Core `DOC_CLASS` reference
codes. Neither a legacy profile nor its instruction is an executable recipe.

## Scanner Lifecycle

The service is scheduled every 30 seconds with `run_on_start` enabled. A
non-blocking process-local lock prevents overlapping ticks in one process; the
Core service manager's database lease prevents multiple managed owners from
running the same service concurrently.

For each enabled location, the scanner:

1. verifies that the configured root is a directory;
2. enumerates direct children or recursive descendants;
3. rejects symlinks and non-regular files;
4. applies hidden-file and glob ignores;
5. applies the optional extension allowlist;
6. records size and nanosecond modification time;
7. waits until both values remain unchanged for `stability_seconds`;
8. checks for an existing durable observation before hashing;
9. hashes the file in bounded chunks;
10. re-stats it and defers enqueue if size or mtime changed during hashing;
11. calls `drop_box_api.enqueue_job`.

Jobs are unique by location, source path, source size, and source modification
time. The observation pre-check avoids unnecessary hashing; the database unique
constraint protects concurrent enqueue attempts.

Scanner-only skips before enqueue have no `drop_job_id`, so missing roots,
ignored files, unstable files, symlinks, and many permission failures appear in
service statistics and logs rather than job-event history.

## Conversion Lifecycle

Queued handoff jobs are marked `processing` before conversion. The converter
stages and hashes the source again, verifies its expected size and SHA-256, then
selects only an allowlisted recipe.

Native formats:

- Markdown: UTF-8 validation, optional BOM removal, newline normalisation, and
  final newline.
- Plain text: the same canonicalisation, represented as canonical Markdown
  text.

Pandoc-backed formats:

- DOCX
- HTML/HTM
- ODT
- RTF
- EPUB

Archive formats are preflighted for entry count, expanded size, per-member
size, compression ratio, encrypted members, traversal paths, symlinks, and
required container structure. HTML and RTF receive signature checks before
Pandoc starts.

Pandoc runs without a shell in a private temporary tree with:

- an executable resolved by the Core-owned command-prerequisite catalogue;
- a controlled `PATH` and minimal environment;
- `--sandbox`;
- a fixed source reader;
- GitHub-flavoured Markdown output with raw HTML disabled;
- no wrapping;
- an empty resource path;
- no user filters, defaults, or document-derived options;
- bounded output, temporary storage, stderr, and runtime.

Pandoc sandbox mode is defence-in-depth, not an operating-system sandbox.

Durable extraction provenance includes the producer plugin's immutable
`producer_knowledge_scope_id`, location and job
ids, source format, converter name/version where applicable, fixed option
identifiers, canonical-output hash, and exact output byte size.

## Drop Box Job States

| Status | Meaning |
| --- | --- |
| `queued` | Durable observation is ready for a handoff attempt or waiting after a transient Core failure. |
| `processing` | The service is converting or calling Core. |
| `deferred_prerequisite` | Pandoc is unavailable, incompatible, or could not be safely probed. |
| `conversion_retry_wait` | A retryable converter failure is waiting for its next attempt. |
| `handed_off` | Core accepted the source and returned an ingestion request id. |
| `failed` | Capture validation or conversion retry exhaustion ended the current job. |
| `quarantined` | The source is unsafe, invalid, or otherwise non-retryable. No file movement occurs. |
| `skipped_disallowed_type` | The extension reached conversion but has no supported recipe. |
| `skipped_duplicate` | A persisted duplicate was skipped. |
| `skipped_too_large` | A persisted source exceeded the applicable job limit. |
| `completed` | Retained compatibility status; Core searchability is the authoritative downstream completion signal. |

Prerequisite deferrals retry every 15 minutes and do not increment conversion
attempts. Unchanged deferral events are rate-limited to one every six hours.

Retryable converter failures wait one minute, then five minutes. The third
attempt becomes terminally failed. A new corrected source observation creates a
new lifecycle; no automatic reopening or unreviewed manual requeue exists.

An unexpected Core/database exception restores the job to `queued` without
persisting raw diagnostics on the job. `ORA-20429` follows that same
retry-preserving path, but the restricted service warning explains that an
existing same-content version has conflicting immutable metadata and lists the
field names only. A `KnowledgeCaptureError` records a terminal failed handoff
for that observation.

## Core Handoff Contract

`DropBoxHandoffJob` supplies `KnowledgeManagedFileCaptureService` with:

- trusted Drop Box location and job ids;
- location root and original source path/name;
- declared source hash, size, and modification time;
- canonical target scope;
- stable source key and legacy identity hint;
- source format and MIME;
- canonical Markdown, hash, size, and output MIME;
- extractor identity/version and bounded metadata;
- classification-tag JSON;
- compatibility profile and untrusted ingestion notes.

Core independently verifies:

- the source resolves beneath the configured root;
- it is a regular file no larger than 100 MiB;
- size and copied SHA-256 match the job;
- source format and MIME agree with the approved Drop Box formats;
- canonical Markdown is non-empty UTF-8 and no larger than 50 MiB;
- canonical hash, size, output MIME, extractor, and metadata agree;
- tags are one to ten distinct uppercase `DOC_CLASS` reference codes;
- ingestion notes are no larger than 16 KiB.

The database then validates active tag identities and canonical scope
eligibility. Scope rejection is redacted at the Core boundary.

## Source Storage and Identity

Core streams the verified original and canonical Markdown through the same
managed-store abstraction. Each payload is promoted to the content-addressed
layout derived from its own hash:

```text
sha256/<first-two>/<next-two>/<full-source-sha256>
```

Existing content with the same hash is verified and reused. The raw original
is authoritative for document-version source identity. Canonical Markdown is
a distinct immutable PRIMARY artefact whose managed key, hash, byte size,
media type, and extraction provenance are registered as one complete output
set in the ingestion transaction. The extraction CLOB is a compatibility
projection and must have the same canonical UTF-8 identity as the PRIMARY.

The stable source key is:

```text
<location_code>:<relative-posix-path-under-location-root>
```

Core stores its hash-derived `drop_box:source:<sha256>` reference. This keeps
absolute deployment paths out of durable identity and produces predictable
revision behaviour:

- same key, changed content: new version of the same document;
- changed relative path: new source/document;
- changed root only: identity preserved;
- changed location code: new source/document.

Legacy job-based source references are migrated only when one safe,
collision-free match can be proved.

## Core Worker Lifecycle

After successful handoff, Drop Box records
`knowledge_ingestion_request_id` and stops owning downstream processing.

The synthetic Core `orac_core:knowledge_ingestion` service:

1. claims the oldest queued, due retry, or expired-lease request;
2. verifies each registered chunkable managed member by logical key, hash, and
   byte size without following symlinks;
3. chunks PRIMARY and MANIFEST members as canonical Markdown and TABLE members
   as complete CSV records, using the legacy CLOB path only when no artefacts
   exist;
4. creates or reuses one artefact-aware chunk set per member;
5. persists chunks with text hashes, source spans, and bounded Markdown or
   spreadsheet provenance;
6. embeds every chunk with the configured provider and dimensions;
7. completes only when the output set is complete, searchable chunks exist,
   and every searchable chunk has a matching embedding.

Core statuses are `QUEUED`, `PROCESSING`, `RETRY_WAIT`, `COMPLETED`, and
`FAILED`. Worker errors are recorded under bounded error codes and retry policy.
A missing payload cannot be marked complete.

## Classification, Retrieval, and Grounding

Classification tags and ingestion notes have no behavioural authority:

- they do not select native or Pandoc conversion;
- they do not alter chunk sizes, overlap, or embedding models;
- they do not influence retrieval ranking or scope authorisation;
- they do not enter privileged prompts;
- they do not influence plugin or dialogue routing;
- they are never executed.

Core projects tags into retrieval provenance and includes selected tag values
with bounded source metadata. Retrieved chunk text remains untrusted evidence
under the Core grounding boundary.

Dialogue retrieval independently requires:

- `[knowledge.dialogue].enabled` (enabled in the shipped configuration);
- an authenticated active principal;
- an active eligible canonical project or plugin scope;
- an effective RAG usage privilege for the authenticated principal and scope;
- compatible stored embedding identity/dimensions;
- lexical relevance and evidence-budget checks.

## APEX and Diagnostic Boundary

Drop Box App 10020 reads approved admin views and writes through
`drop_box_admin_api`; it does not perform direct table DML. Its activity report
joins an approved Core ingestion projection by request id while keeping the
Drop Box and Core states separate.

Administrator-visible diagnostics contain stable reason codes and bounded safe
messages. Raw Pandoc stderr, executable paths, stack traces, credentials,
ingestion notes, unrestricted event payloads, document text, and vectors are
not rendered.

## Failure, Retry, and Reconciliation Boundary

A Core/database failure after managed promotion restores the Drop Box job to a
retryable state. The promoted immutable object is retained; the next attempt
verifies and reuses it instead of creating another physical copy. Concurrent
promoters similarly converge on one verified object. An interrupted promotion
may leave a store-owned temporary entry, while a completed promotion without a
database reference may later appear as an unregistered object.

Missing or corrupt registered objects, stale temporary entries, confirmed
orphans, unsafe layout, symlinks, and database-lineage failures are reported by
Core's bounded read-only reconciliation workflow. Recent unregistered objects
and unresolved concurrent changes produce `INCOMPLETE`, not a premature orphan
classification. Stable divergence produces `BLOCKED`.

Neither Drop Box nor reconciliation automatically repairs, registers, moves,
quarantines, deletes, rewrites, or recovers managed content. Use the
[Core maintenance guide](../../../docs/knowledge-maintenance.md#read-only-operational-reconciliation)
for inspection. Any recovery action requires a separately authorised and
audited workflow.

## Deferred Work

The current lifecycle deliberately excludes:

- post-processing source movement, deletion, or physical quarantine;
- manual terminal-job reopening without a separately reviewed audit workflow;
- PDF/OCR, spreadsheets, presentations, remote acquisition, and embedded media;
- model-generated transformations;
- automatic regeneration of historical completed versions when a converter or
  chunker changes;
- native Oracle vector search and a production semantic embedding migration.

Raw-binary model submission and model-capability routing are Phase 2 work.
Drop Box currently hands Core canonical Markdown only; future spreadsheet
artefact shapes are supported by Core lineage but spreadsheet conversion is
not a current Drop Box capability.
