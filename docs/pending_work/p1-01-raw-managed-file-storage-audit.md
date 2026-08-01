# P1-01 Raw Managed-File Storage Audit

## Status and scope

Status: completed on 26 July 2026.

This audit records the current raw managed-file storage contract, the
development-environment observations, the exact implementation and schema
seams, the known defects and open deployment questions, and the requirements
for a future read-only environment preflight.

P1-01 is an audit and documentation item. It does not implement storage
changes, database changes, migration, reconciliation, cleanup, or regression
tests. Those changes are allocated to downstream backlog items in
[Orac Document Materialisation and Binary Model Routing Enhancements](orac_document_materialisation_enhancements_plan.md).

## Verified current contract

The checked-out implementation establishes the following current-state
contract:

- Core stores raw originals beneath `[knowledge].managed_root`.
- The current locator shape is:

  ```text
  sha256/<first-two-hash-characters>/<next-two-hash-characters>/<full-sha256>
  ```

- `orac_core.knowledge_document_versions.content_uri` currently records that
  managed-root-relative key. It is not an absolute host path.
- Managed raw objects are immutable and extensionless. A future attachment or
  materialisation service may give a short-lived copy a safe filename or
  extension without changing the managed object.
- Physical payload identity is global by SHA-256. Separate documents with the
  same bytes can retain separate document-version lineage while referring to
  the same physical key.
- Drop Box sends every currently supported raw media type through the same Core
  capture and promotion path. Format-specific normalisation does not create a
  separate raw storage route.
- Capture hashes the source while copying it to a temporary file, compares the
  copied hash with the Drop Box observation, and verifies the promoted or
  reused object.
- The Core worker verifies the raw object hash before processing a claimed
  ingestion request.

This is a record of current behaviour. It does not decide the future durable
storage-key abstraction, whether raw originals will also receive general
artefact rows, or how database shape validation will be divided from owning-API
canonical validation. Those decisions belong to P1-02 and P1-03.

## Current data flow

```text
Drop Box scan and source hash
  -> format validation and canonical Markdown production
  -> Core source-path, size, hash, MIME, and normalised-content validation
  -> <managed-root>/.tmp/capture-*.tmp
  -> <managed-root>/sha256/<two>/<two>/<sha256>
  -> orac_code.knowledge_ingestion_api.submit_managed_file
  -> document version, extraction, tags, and ingestion request
  -> Core worker locator resolution and raw hash verification
```

Filesystem promotion occurs before database registration commits. A database
failure cannot roll back the promoted object, so an unreferenced but valid
object can remain for a later idempotent retry or future reconciliation.

## Exact implementation and schema seams

### Drop Box handoff

- `plugins/drop_box/service.py`
  - `DropBoxService._handoff_jobs`
  - constructs the Core capture service and submits each converted job
- `plugins/drop_box/models.py`
  - `DropBoxHandoffJob.to_capture_request`
  - transfers the observed raw identity, location boundary, source metadata,
    canonical Markdown, extractor provenance, and classification tags

### Core storage and registration

- `src/orac_core/knowledge/capture.py`
  - `KnowledgeManagedFileCaptureService.capture_drop_box_file`
  - `_validate_source_path`
  - `_copy_to_temp`
  - `_install_temp_file`
  - `_content_uri`
  - `_content_path`
  - `_sha256_file`
- `src/orac_core/knowledge/repository.py`
  - `KnowledgeIngestionRepository.submit_managed_file`
  - commits the `orac_code.knowledge_ingestion_api.submit_managed_file` call
- `src/orac_core/knowledge/worker.py`
  - `KnowledgeIngestionService._process_request`
  - joins `content_uri` to its configured root and verifies the raw hash
  - `_sha256_file` duplicates the capture-side hashing implementation

### Database lineage and access

- `orac_core.knowledge_document_versions`
  - `content_sha256`, `content_uri`, `mime_type`, `original_filename`,
    `byte_size`, and `source_modified_on`
- `orac_code.knowledge_ingestion_api.submit_managed_file`
  - validates submission metadata and creates or reuses document lineage
  - currently accepts the locator as a caller parameter
  - currently updates the locator when reusing an existing version
- `orac_api.knowledge_document_versions_v`
  - API projection of raw document-version metadata
- `orac_code.knowledge_ingestion_requests_v` and
  `orac_code.knowledge_searchable_chunks_v`
  - project raw locator and provenance into runtime-facing reads
- `ORAC` and `ORAC_PLUGIN`
  - both currently have execute on the complete
    `orac_code.knowledge_ingestion_api` package

## Development-environment observations

The audit inspected the development database and
`${ORAC_HOME}/var/knowledge/content` read-only on 26 July 2026.

| Observation | Result |
| --- | ---: |
| Document versions | 54 |
| Ingestion requests | 54 |
| Distinct raw hashes | 51 |
| Distinct raw locators | 51 |
| Rows matching the current hash-shard locator shape | 54 |
| Referenced objects present and hash-correct | 51 |
| Referenced objects with malformed shard placement | 0 |
| Payload hashes referenced by two documents | 3 |
| Unreferenced promoted objects | 2 |
| Stale capture temporary files | 102 |
| Distinct hashes among stale temporary files | 17 |
| Repetitions of each stale temporary payload | 6 |
| Focused tests passing | 33 |

All visible source types in this snapshot were `DROP_BOX`, and all visible raw
MIME types were `text/markdown`. The implementation supports additional raw
formats, but the snapshot does not prove that those formats have been deployed
and captured in every environment.

### Reproduction queries and checks

The database counts were obtained from the full
`orac_core.knowledge_document_versions` table using a read-only administrative
connection. An application-role check can use
`orac_code.knowledge_ingestion_requests_v`.

```sql
select count(*) as total_versions,
       count(distinct content_sha256) as distinct_hashes,
       count(distinct content_uri) as distinct_uris,
       sum(
         case
           when content_uri =
                'sha256/'
                || substr(content_sha256, 1, 2)
                || '/'
                || substr(content_sha256, 3, 2)
                || '/'
                || content_sha256
           then 1
           else 0
         end
       ) as current_layout_rows
  from orac_core.knowledge_document_versions;
```

Shared physical payloads were identified with:

```sql
select content_sha256,
       content_uri,
       count(*) as version_count,
       count(distinct document_id) as document_count
  from orac_core.knowledge_document_versions
 group by content_sha256,
          content_uri
having count(distinct document_id) > 1
 order by content_sha256;
```

Filesystem verification enumerated regular files beneath the current
`sha256` tree, checked each filename and shard directories against its SHA-256,
rehashes every file, and compared the resulting hash set with the distinct
database hash set. Temporary files were enumerated separately beneath `.tmp`
and grouped by calculated hash and modification date. The checks made no
filesystem or database changes.

These commands establish the current-layout classification only. They are not
a proposed database constraint or a decision that the complete path shape must
remain the future durable storage-key format.

## Findings by confidence

### Confirmed defects

| Finding | Evidence and impact | Downstream owner |
| --- | --- | --- |
| Divergent root selection | The worker reads `[knowledge].managed_root`; default Drop Box capture uses a project-relative fallback without reading that setting. A non-default configuration can split writes and reads. | P1-03 |
| Unsafe database-locator resolution | The worker joins the database value directly to the root without rejecting absolute paths, traversal, malformed keys, or symlink escape. | P1-03 |
| Non-exclusive, non-durable promotion | `shutil.move` does not establish a no-clobber contract, can fall back to copy/delete across filesystems, and is not followed by file and directory durability synchronisation. | P1-03 |
| Concurrent temporary-file cleanup race | The caller decides whether the temporary file was consumed using an existence observation made before installation. A concurrent winner can make the installer reuse the destination while the caller drops responsibility for its temporary file. | P1-03 |
| Duplicated storage logic | Locator/path handling and file hashing are split across capture and worker code instead of one owning abstraction. | P1-03 |
| Missing read-side size verification | The worker verifies the registered hash but not the registered byte size. | P1-03 |
| Unconstrained owning-API locator input | `submit_managed_file` requires only a nonempty locator and does not prove its relationship to the submitted hash. The future validation boundary remains undecided. | P1-02 |
| Existing locator can be mutated | Reuse of an existing document version updates `content_uri`, weakening the intended immutable storage-reference contract. The future authority model remains undecided. | P1-02 |
| Existing-environment compatibility is unknown | The development database is canonical under the current scheme, but other deployed databases and stores were not inspected. | P1-05 |
| Reconciliation is absent | There is no supported inventory, corruption report, stale-temp report, or orphan reconciliation workflow. | P1-09 |
| Lifecycle documentation and regression coverage are incomplete | Current documentation describes intended behaviour, while concurrency, alternate roots, traversal, symlinks, size mismatch, registration failure, and reconciliation lack complete regression evidence. | P1-10 |

### Tentative inferences

- The 102 stale temporary files are strongly consistent with the confirmed
  concurrent install/cleanup race: 17 distinct payloads each have six stale
  copies. Historical process evidence is insufficient to prove the precise
  originating executions.
- The two unreferenced promoted objects are consistent with database failure
  after successful promotion. Their original registration attempts cannot be
  reconstructed from the remaining metadata.

These observations must not be used to delete or rewrite content.

### Unresolved deployment questions

- Do non-development environments contain legacy, absolute, plugin-owned, or
  otherwise noncanonical `content_uri` values?
- Which target filesystems and deployment layouts must the future atomic
  promotion mechanism support?
- What grace period, quarantine policy, approval, and audit requirements apply
  before unreferenced objects or stale temporary files may be removed?
- Does `ORAC_PLUGIN` require execute on the complete ingestion package, or
  should the current visibility/invocation need be replaced by a narrower
  interface?

## Required read-only environment preflight

P1-01 defines the report contract. P1-09 owns implementation of a reusable
tool after P1-02 and P1-03 settle the storage-key and managed-store contracts.
The report must include:

- effective managed-root value, its configuration source, and its resolved
  filesystem identity;
- database document-version row count, distinct hash count, and distinct
  locator count;
- classification of locators against the current deployed layout, clearly
  separated from any future canonical storage-key decision;
- payload hashes referenced by multiple versions or documents;
- missing, unreadable, corrupt, and byte-size-mismatched referenced objects;
- malformed shard layouts, unsafe path components, non-regular objects, and
  symlinks;
- disk objects with no database reference;
- temporary-file count, age distribution, total bytes, and distinct hashes;
- filesystem facts required to select and verify a future atomic promotion
  primitive, including whether temporary and final areas are on the same
  filesystem;
- a bounded human-readable summary;
- machine-readable reason codes and counts;
- non-sensitive diagnostics that do not expose unrestricted host paths or
  document content.

The preflight must be strictly read-only. It must not delete, quarantine,
relocate, rename, repair, rewrite database rows, or change permissions. Any
future repair operation must be a separate, explicit, auditable workflow.

## Downstream allocation

### P1-02: Artefact model and authority

P1-02 decides:

- whether raw authority remains solely on document-version columns or is also
  represented by a general artefact entity;
- the durable storage-key abstraction;
- the authority relationship between raw columns, extraction content, and
  future artefact rows;
- which storage-key properties belong in database shape validation and which
  require owning-API canonical validation;
- how immutable locator semantics are enforced.

P1-02 must not assume a database check constraint containing the complete
current hash-shard path before these decisions are made.

### P1-03: Managed-store implementation

P1-03 owns:

- a reusable Core-managed store abstraction; `managed_store.py` is a proposed
  seam, not a fixed filename;
- one common, validated root configuration for capture and worker use;
- central locator construction, parsing, containment, and symlink defence;
- atomic no-clobber promotion with explicit filesystem compatibility;
- installed-versus-reused outcomes under concurrent identical submissions;
- hash and byte-size verification at write and read boundaries;
- deterministic cleanup of temporary files on success and failure.

### P1-05: Existing-environment compatibility

P1-05 owns:

- running the P1-09 preflight in each target environment;
- classifying legacy and noncanonical locators and store layouts;
- choosing a bounded compatibility or migration strategy;
- proving corresponding bytes and the intended managed object before any
  locator rewrite;
- keeping existing searchable documents available during transition.

### P1-09: Reconciliation and observability

P1-09 owns:

- implementation of the reusable read-only preflight defined by this audit;
- inventory, missing-object and corruption detection;
- stale temporary-file reporting;
- unreferenced-object reporting and reconciliation;
- bounded metrics, reason codes, and operator diagnostics;
- report-only initial behaviour.

Quarantine or deletion requires a separately approved retention and audit
policy.

### P1-10: Documentation and regression coverage

P1-10 owns:

- lifecycle, configuration, recovery, operational, and security documentation
  reflecting implemented downstream behaviour;
- tests for identical-content reuse, concurrency, interrupted promotion,
  alternate roots, hash and size mismatch, path escape, symlinks, database
  failure after promotion, retry reuse, and reconciliation reporting;
- preservation of documentation link validation and the existing focused test
  baseline.

### Separate least-privilege security decision

The `ORAC_PLUGIN` execute grant on the complete
`orac_code.knowledge_ingestion_api` is a separate security finding. A reviewed
decision must choose one of:

- retain the grant with an explicit least-privilege justification;
- replace it with a narrower package or status interface;
- revoke it after removing the dependency.

P1-01 makes no grant or runtime change.

## P1-01 completion statement

P1-01 is complete when this audit and the linked backlog allocations are
reviewed and merged. Completion does not require a reusable preflight tool.
Implementing that tool before P1-02 and P1-03 decide the future storage
contracts would risk duplicating or prematurely fixing unsettled rules.
