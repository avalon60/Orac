# P1-02 Normalised Artefact and Chunk-Lineage Model

## Status and scope

Status: completed on 26 July 2026.

P1-02 selects and documents the durable normalised-artefact model, the
member-level chunk-lineage extension, the storage-key contract, the ownership
and compatibility boundaries, and the exact downstream implementation
sequence.

P1-02 is a design and documentation item. It does not create or alter database
objects, packages, grants, migrations, Python code, configuration, or tests.
Implementation is allocated to the downstream backlog items in
[Orac Document Materialisation and Binary Model Routing
Enhancements](orac_document_materialisation_enhancements_plan.md).

## Repository-grounded current state

The checked-out repository establishes these relevant facts:

- `orac_core.knowledge_document_versions` owns the current raw-original
  identity, hash, locator, MIME type, filename, byte size, source timestamp,
  and source format.
- `orac_core.knowledge_extractions` represents one extractor run for a
  document version and currently stores one required `extracted_text` CLOB and
  its SHA-256.
- `orac_core.knowledge_chunk_sets` currently refers only to `extraction_id`.
- `kn_chset_uk1` currently identifies a chunk set by extraction, chunker,
  chunker version, chunk size, and overlap. It cannot distinguish two
  separately chunked members of one extraction.
- `orac_code.knowledge_ingestion_api.create_chunk_set` and
  `KnowledgeIngestionRepository.create_chunk_set` expose that same
  extraction-only identity.
- `orac_code.knowledge_searchable_chunks_v`, the Python retrieval models, and
  the grounding pack expose document, extraction, chunk, and raw locator
  provenance but no normalised member identity.
- `knowledge_chunks.span_start` and `span_end` currently describe offsets in
  the text supplied to the Markdown chunker.
- The worker currently chunks `knowledge_extractions.extracted_text`, falling
  back to the raw managed payload only for the legacy native-text path.
- The Core schema controller installs `table`, `index`, primary and unique
  constraints, other constraints, `migration`, foreign keys, triggers, seed
  data, and comments in that order. It has no `annotation` directory or
  controller stage.

The 26 July 2026 development database contained 54 document versions and 48
existing extraction rows. All 48 extractions used the legacy `core_text_v1`
identity and had null values in the later output MIME and extractor-metadata
columns. The additive model must therefore tolerate CLOB-only legacy
extractions and chunk sets without requiring deployment-time backfill.

## Considered models

### Extraction storage columns

Adding one hash, locator, MIME type, and size directly to
`knowledge_extractions` would be a small change, but it cannot represent a
Markdown workbook manifest plus multiple independently addressable and
chunkable CSV members without repeating columns or embedding an ungoverned
package structure in JSON.

This option is rejected.

### Separate package and package-member entities

A package entity and member entity would represent spreadsheet outputs
explicitly, but `knowledge_extractions` already supplies the extractor-run and
output-set boundary. Adding another package identity before nested packages or
cross-extraction packages exist would duplicate that responsibility.

This option is rejected for Phase 1.

### General immutable artefacts owned by an extraction

A general artefact child table supports one or many immutable normalised
members while retaining the existing document-version, extraction, chunk-set,
and chunk chain. The extraction remains the output-set identity, and each
chunk set can point at the precise member it processed.

This option is selected.

## Authority model

Authority is divided by responsibility:

- `knowledge_document_versions` owns raw-original identity and raw storage
  metadata.
- `knowledge_extractions` owns the extractor run and output-set identity.
- `knowledge_artefacts` owns durable normalised bytes and member-level
  provenance.
- `knowledge_extractions.extracted_text` remains a transitional compatibility
  projection and the input for legacy CLOB-only chunking.
- `knowledge_chunk_sets` owns chunking results for either a specific
  normalised artefact or a legacy extraction CLOB.

The extraction CLOB and a managed artefact are not independent authorities for
the same durable bytes. For a PRIMARY or MANIFEST artefact, the artefact is the
durable-byte authority and the CLOB is a compatibility projection whose
canonical UTF-8 identity must agree with that artefact.

Existing CLOB-only extractions remain valid and searchable. P1-05 decides and
executes their controlled backfill after P1-03 provides the managed-store
implementation.

## Selected artefact entity

The selected table is:

```text
orac_core.knowledge_artefacts
```

The proposed and reserved table abbreviation is:

```text
kn_artf
```

Each row contains:

| Column | Datatype | Contract |
| --- | --- | --- |
| `artefact_id` | `number` identity | Positive primary key. |
| `extraction_id` | `number` | Required owner and producer-run lineage. |
| `artefact_role_code` | `varchar2(50 char)` | Controlled member role. |
| `media_type` | `varchar2(255 char)` | Canonical output media type. |
| `content_sha256` | `varchar2(64 char)` | SHA-256 of the exact managed bytes. |
| `storage_key` | `varchar2(71 char)` | Logical content-store key. |
| `byte_size` | `number` | Exact managed-byte size. |
| `logical_name` | `varchar2(200 char)` | Safe deterministic member basename. |
| `member_ordinal` | `number` | One-based ordering within the output set. |
| `metadata_json` | `json` | Optional bounded member provenance. |
| `created_by` | `varchar2(128 char)` | Registration principal or process. |
| `created_on` | `timestamp with time zone` | Registration timestamp. |

Artefact rows are append-only. They do not have a mutable lifecycle or
verification-state column. Missing, corrupt, or unavailable storage is derived
by verified reads and P1-09 inventory rather than stored as state that can
become stale.

The Phase 1 roles are:

- `PRIMARY`: canonical Markdown for a single-file output;
- `MANIFEST`: canonical Markdown manifest for a multi-file output;
- `TABLE`: independently chunkable CSV member;
- `METADATA`: non-chunkable JSON sidecar.

The database model enforces:

- `kn_artf_pk` on `artefact_id`;
- `kn_artf_kn_ext_fk1` from `extraction_id` to
  `knowledge_extractions.extraction_id`;
- `kn_artf_uk1` on `(extraction_id, logical_name)`;
- `kn_artf_uk2` on `(extraction_id, member_ordinal)`;
- `kn_artf_uk3` on `(extraction_id, artefact_id)` for the composite
  chunk-source relationship;
- an at-most-one PRIMARY-or-MANIFEST function-based unique index;
- positive identity and ordinal values;
- lower-case 64-character SHA-256;
- non-negative byte size;
- controlled role values;
- safe, non-path logical-name shape;
- `storage_key = 'sha256:' || content_sha256`.

Storage keys are deliberately non-unique across lineage rows. Two source
members with identical bytes may share one physical content-addressed object
while retaining distinct document, extraction, logical-member, and chunk
provenance.

## Output-set completeness and atomic registration

An at-most-one unique index is not the completeness mechanism. New output sets
are registered through one higher-level operation:

```text
orac_code.knowledge_artefact_api.register_output_set(
  p_extraction_id,
  p_output_set_json
) return clob
```

There is no runtime-facing per-member `register_artefact` operation. A
per-member insert helper remains private to the package body, and
`orac_api.knowledge_artefacts_tapi` exposes insert only to `ORAC_CODE`.

The registration envelope contains:

```json
{
  "schema_version": 1,
  "set_kind": "SINGLE",
  "members": [
    {
      "role": "PRIMARY",
      "media_type": "text/markdown; charset=utf-8",
      "content_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "storage_key": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "byte_size": 1234,
      "logical_name": "primary.md",
      "ordinal": 1,
      "metadata": null
    }
  ]
}
```

`set_kind` is exactly `SINGLE` or `SPREADSHEET`. The return CLOB has this
bounded shape and does not expose storage paths:

```json
{
  "reused": false,
  "members": [
    {
      "artefact_id": 101,
      "logical_name": "primary.md",
      "ordinal": 1
    }
  ]
}
```

The contract permits 1 to 256 members, limits the complete request to 1 MiB,
and limits each member metadata object to 16 KiB.

Before performing DML, the owning API:

- parses and validates the entire bounded envelope;
- locks the extraction row;
- requires exactly one PRIMARY or MANIFEST;
- requires unique logical names and contiguous ordinals starting at one;
- requires SINGLE sets to contain a PRIMARY and no TABLE members;
- requires spreadsheet sets to contain a MANIFEST and at least one TABLE;
- validates every immutable descriptor and role/media combination;
- validates PRIMARY or MANIFEST identity against the extraction CLOB;
- compares the complete submitted set with any existing registered set.

When no members exist, every member is inserted within the one package call.
When members already exist, the API returns the existing member identities
only if the complete set agrees. Missing, additional, or conflicting members
cause an idempotency conflict. The comparison treats supported JSON fields
semantically rather than comparing unnormalised JSON source text.

The package does not commit. For initial ingestion,
`knowledge_ingestion_api.submit_managed_file` invokes output-set registration
inside the existing submission transaction, so the extraction, request, and
complete artefact set commit together. P1-05 backfill commits one complete
output set per call. An unhandled registration error rolls back every member
insert made by that call.

The package also exposes:

```text
orac_code.knowledge_artefact_api.assert_complete_set(
  p_extraction_id
)
```

`assert_complete_set` is called after registration and by
`knowledge_ingestion_api.complete_request`. It proves the required primary
member, role distribution, contiguous membership, immutable identities, and
PRIMARY or MANIFEST compatibility with the extraction CLOB.

Incomplete sets must not complete an ingestion request. The searchable-chunk
and request-status business views also fail closed so that an incomplete set
is neither searchable nor materialisable even if request state is
inconsistent.

No separate persisted `complete_yn` is required. A future
`orac_code.knowledge_artefact_sets_v` derives structural member counts and
completeness for completion, retrieval, materialisation, and operator
reporting.

## Canonical text compatibility

For a PRIMARY or MANIFEST artefact:

- `media_type` is `text/markdown; charset=utf-8`;
- managed bytes are exactly `extracted_text` encoded as UTF-8;
- no UTF-8 BOM is present;
- CRLF and bare CR have been converted to LF;
- at least one terminal LF is present;
- `content_sha256` equals `knowledge_extractions.text_sha256`;
- `byte_size` equals the UTF-8 byte length calculated from the CLOB.

The owning database API reuses the existing UTF-8 identity calculation seam
and rejects a CLOB beginning with U+FEFF, containing CR, or lacking a terminal
LF. P1-03 verifies the registered hash and size against the managed object.

For a single-file Markdown output, PRIMARY is the chunk source.

For a spreadsheet output, `extracted_text` contains the Markdown workbook
manifest and agrees with the MANIFEST artefact. The MANIFEST and every TABLE
member can be chunked and embedded independently.

## Artefact-backed chunk lineage

The downstream schema adds:

```text
knowledge_chunk_sets.source_artefact_id
```

The column is nullable:

- null means the chunk set was produced from the extraction CLOB under the
  legacy compatibility path;
- non-null identifies the precise artefact whose decoded content was chunked.

The schema also adds an internal virtual value:

```text
source_artefact_key generated always as
  (nvl(source_artefact_id, -1))
```

It is not exposed through the API view. The negative sentinel is safe because
artefact identities are constrained to positive values.

The revised `kn_chset_uk1` is:

```text
extraction_id
+ source_artefact_key
+ chunker_code
+ chunker_version
+ chunk_size_tokens
+ overlap_tokens
```

This retains one idempotent legacy CLOB chunk set for a given chunking
configuration while distinguishing independently chunked members of one
extraction.

Cross-extraction references are prevented with:

```text
kn_chset_kn_artf_fk1
  (extraction_id, source_artefact_id)
  -> knowledge_artefacts(extraction_id, artefact_id)
```

Oracle does not enforce the composite FK when the nullable artefact component
is null, which preserves existing CLOB-only rows. When the component is
present, the FK proves both artefact existence and extraction ownership. The
existing chunk-set-to-extraction FK remains in place.

The owning `create_chunk_set` API adds
`p_source_artefact_id default null` after the existing parameters. It:

- permits null only when the extraction has no registered artefacts;
- rejects cross-extraction artefacts in addition to the database FK;
- permits PRIMARY, MANIFEST, and TABLE sources;
- rejects METADATA sources;
- uses the complete revised idempotency key for reuse;
- fails rather than returning an unrelated member's chunk set.

## Spreadsheet member metadata

TABLE artefacts use this version-one metadata shape:

```json
{
  "schema_version": 1,
  "sheet_name": "Forecast",
  "table_name": "Quarterly forecast",
  "source_cell_range": "A1:F120",
  "header_rows": [1, 2],
  "hidden_sheet": false
}
```

The contract is:

- `schema_version` is the integer `1`;
- `sheet_name` is required and limited to 255 Unicode characters;
- `table_name` is optional and, when present, limited to 255 Unicode
  characters;
- `source_cell_range` is a required canonical A1 range no longer than 100
  ASCII characters;
- `header_rows` is a required array of at most 32 distinct positive row
  numbers contained by the source range;
- `hidden_sheet` is a required JSON boolean;
- unknown fields are rejected for schema version 1.

Worksheet and table names are untrusted provenance. They never form storage
keys or paths.

`logical_name` is a deterministic machine-facing basename containing only
lower-case ASCII letters, digits, `.`, `_`, and `-`. It is generated from
member type and ordinal rather than worksheet or table text. Examples are:

```text
primary.md
workbook-manifest.md
sheet-0001-table-0001.csv
metadata-0001.json
```

For TABLE chunks, `knowledge_chunks.chunk_metadata_json` records:

- `schema_version`;
- `source_row_start`;
- `source_row_end`;
- the chunk-specific `source_cell_range`.

The chunk's `span_start` and `span_end` remain offsets in the decoded CSV
member. Workbook, sheet, table, member range, header, and hidden-sheet facts
come from the source artefact; the narrower row and cell range comes from the
chunk.

## Retrieval provenance

`orac_code.knowledge_searchable_chunks_v` must join a non-null chunk source to
`orac_api.knowledge_artefacts_v` and expose:

- `source_artefact_id`;
- artefact role, logical name, media type, hash, and member ordinal;
- sheet name, table name, member source range, header rows, and hidden-sheet
  state where applicable;
- chunk-specific source row and cell range.

Legacy chunk sets expose null artefact and spreadsheet-member fields while
retaining the existing document, extraction, span, and chunk provenance.

The Python repository query, `KnowledgeSearchResult`, retrieval validation,
grounding evidence entries, and safe provenance maps must carry the same
fields. Untrusted sheet and table labels remain data and are not promoted into
instructions, paths, or authority-bearing identifiers.

The current `req.status_code = 'COMPLETED'` and `stage_code = 'COMPLETED'`
filters remain. Artefact-backed rows additionally require a complete output
set and a valid source artefact. Legacy rows require no registered artefacts
and a null chunk source.

## Storage-key contract and compatibility

The durable storage key is:

```text
sha256:<64-lowercase-hex>
```

It identifies bytes independently from the configured root and physical shard
layout. Raw and normalised bytes use the same global hash identity; lineage
remains in the database rows that reference the key.

P1-03 implements dual resolution:

- legacy `sha256/aa/bb/<hash>` database locators;
- new `sha256:<hash>` logical keys.

Both resolve through the same controlled managed-store abstraction. All new
registrations use the logical form. The owning API and P1-03 store must not
create new legacy shard-path locators.

P1-05 performs controlled raw-locator migration only after the environment
preflight and proof that each locator resolves to the intended hash and bytes.
That migration is the one explicit exception to raw-version locator
immutability.

After migration, ordinary runtime reuse must never mutate the raw locator,
hash, MIME type, byte size, or source format. A disagreement is an idempotency
conflict, not an update opportunity.

The new artefact table can enforce the complete logical key relationship from
its first row. No full physical shard-path check is added to
`knowledge_document_versions`.

## Validation boundary

Database shape constraints own:

- required values and datatype limits;
- positive identities and ordinals;
- hash syntax;
- logical-key-to-hash equality;
- byte-size lower bound;
- controlled role values;
- safe logical-name shape;
- extraction and member referential integrity;
- member name, ordinal, primary-role, and chunk-set uniqueness.

The owning `ORAC_CODE` API owns:

- complete-set atomicity and exact-one completeness;
- role/media combinations;
- canonical UTF-8 compatibility;
- bounded versioned metadata;
- safe deterministic logical-name construction;
- complete-set and chunk-set idempotency conflicts;
- legacy-null versus artefact-backed chunking eligibility;
- completeness before request completion.

P1-03 owns:

- key parsing and physical path resolution;
- root containment and symlink defence;
- atomic promotion;
- managed-byte hash and size verification;
- dual legacy/logical-key resolution.

P1-09 owns read-only inventory and reports missing, corrupt, incomplete,
unreferenced, or otherwise inconsistent objects and rows.

## Exact downstream database manifest

P1-02 records this downstream implementation sequence. It does not execute it.

### Abbreviation and Core data objects

Add:

- `docs/agent-guardrails/table-abbreviations.csv`
  - `orac_core,knowledge_artefacts,kn_artf`
- `resources/db/schema/orac_core/table/knowledge_artefacts.sql`
- `resources/db/schema/orac_core/index/kn_artf_pk.sql`
- `resources/db/schema/orac_core/index/kn_artf_uk1_idx.sql`
- `resources/db/schema/orac_core/index/kn_artf_uk2_idx.sql`
- `resources/db/schema/orac_core/index/kn_artf_uk3_idx.sql`
- `resources/db/schema/orac_core/index/kn_artf_fidx1.sql`
- `resources/db/schema/orac_core/index/kn_artf_idx1.sql`
- `resources/db/schema/orac_core/constraint_pk/kn_artf_pk.sql`
- `resources/db/schema/orac_core/constraint_uc/kn_artf_uk1.sql`
- `resources/db/schema/orac_core/constraint_uc/kn_artf_uk2.sql`
- `resources/db/schema/orac_core/constraint_uc/kn_artf_uk3.sql`
- `resources/db/schema/orac_core/constraint_other/kn_artf_id_ck.sql`
- `resources/db/schema/orac_core/constraint_other/kn_artf_hash_ck.sql`
- `resources/db/schema/orac_core/constraint_other/kn_artf_storage_key_ck.sql`
- `resources/db/schema/orac_core/constraint_other/kn_artf_size_ck.sql`
- `resources/db/schema/orac_core/constraint_other/kn_artf_role_ck.sql`
- `resources/db/schema/orac_core/constraint_other/kn_artf_ordinal_ck.sql`
- `resources/db/schema/orac_core/constraint_other/kn_artf_logical_name_ck.sql`
- `resources/db/schema/orac_core/constraint_fk/kn_artf_kn_ext_fk1.sql`
- `resources/db/schema/orac_core/comment/knowledge_artefacts.sql`

`kn_artf_fidx1` is the at-most-one PRIMARY-or-MANIFEST index.
`kn_artf_idx1` indexes `storage_key` for inventory and reference lookups.

No `orac_core/annotation/knowledge_artefacts.sql` is included. The repository
has no Core annotation directory, approved local vocabulary, or annotation
controller stage. P1-02 does not imply otherwise or expand its scope by
introducing that infrastructure.

### Chunk-set evolution

Add:

- `resources/db/schema/orac_core/migration/knowledge_chunk_set_artefact_lineage.sql`
- `resources/db/schema/orac_core/constraint_fk/kn_chset_kn_artf_fk1.sql`

The new migration changeset:

1. adds nullable `source_artefact_id`;
2. adds the virtual `source_artefact_key`;
3. drops the executed legacy `kn_chset_uk1` definition and its backing index;
4. recreates the index and `kn_chset_uk1` with the artefact-aware key.

Its rollback may restore the legacy unique key only after a precondition proves
that no chunk set has a non-null `source_artefact_id`. The composite FK is
installed later by the existing `constraint_fk` controller stage and rolls
back before the migration under normal reverse-order rollback.

Update:

- `resources/db/schema/orac_core/comment/knowledge_ingestion.sql`
  - document the nullable source and legacy meaning.

The current Core controller order remains valid:

```text
table
-> index
-> primary/unique/other constraints
-> migration
-> foreign keys
-> triggers
-> seed data
-> comments
```

Fresh installation initially creates the legacy chunk-set key from the
existing source scripts, then the new migration replaces it. Existing
environments receive only the new preconditioned migration changeset.

### API layer

Add:

- `resources/db/schema/orac_api/privilege/knowledge_artefacts_core_access.sql`
- `resources/db/schema/orac_api/view/knowledge_artefacts_v.sql`
- `resources/db/schema/orac_api/package_spec/knowledge_artefacts_tapi.sql`
- `resources/db/schema/orac_api/package_body/knowledge_artefacts_tapi.sql`
- `resources/db/schema/orac_api/grant/knowledge_artefacts_api_access.sql`

Update:

- `resources/db/schema/orac_api/view/knowledge_chunk_sets_v.sql`
  - expose `source_artefact_id`, not the virtual key;
- the applicable existing Core-to-API and API-to-Code dependency checks.

The Core grant to `ORAC_API` is `select, insert` for artefacts. The TAPI has an
insert operation only. `ORAC_CODE` receives select on the view and execute on
the TAPI. No update or delete artefact path is added.

### Business layer

Add:

- `resources/db/schema/orac_code/package_spec/knowledge_artefact_api.sql`
- `resources/db/schema/orac_code/package_body/knowledge_artefact_api.sql`
- `resources/db/schema/orac_code/view/knowledge_artefact_sets_v.sql`

Update:

- `resources/db/schema/orac_code/package_spec/knowledge_ingestion_api.sql`
- `resources/db/schema/orac_code/package_body/knowledge_ingestion_api.sql`
- `resources/db/schema/orac_code/view/knowledge_searchable_chunks_v.sql`
- `resources/db/schema/orac_code/view/knowledge_ingestion_requests_v.sql`
- `resources/db/schema/orac_code/grant/orac_code_consumer_package_access.sql`

The new artefact business package is granted to `ORAC` only. P1-02 does not
extend the current `ORAC_PLUGIN` package grant, revoke it, or resolve the
separate least-privilege finding.

The existing schema controllers already include the required privilege, view,
package, and grant directories in the required Core-to-API-to-Code order. No
product-controller or schema-controller change is required by this design.

## Downstream runtime and service changes

### P1-03

- Implement the logical storage key and dual legacy/new resolution.
- Make all new raw and normalised registrations return logical keys.
- Verify exact managed bytes, hash, and size.

### P1-04

- Promote every normalised member before database registration.
- Submit the complete output-set envelope within the ingestion transaction.
- Load and chunk each PRIMARY, MANIFEST, or TABLE artefact independently.
- Pass `source_artefact_id` when creating new chunk sets.
- Retain CLOB-only processing solely for legacy extractions with no artefacts.
- Update repository transaction boundaries so one output-set package call is
  committed only after successful complete-set validation.

### P1-05

- Backfill existing CLOB extractions one complete output set at a time.
- Run the read-only preflight before raw-locator migration.
- Treat proven raw-locator rewrites as the explicit one-time immutability
  exception.

### P1-06

- Resolve normalised content by artefact identity.
- Return member-aware provenance without exposing storage keys as caller
  authority or host paths.
- Reject incomplete, missing, corrupt, or cross-scope members.

### P1-09

- Inventory complete and incomplete output sets.
- Include artefact-to-extraction and chunk-set-to-artefact mismatches in
  report-only reconciliation.

### P1-10

- Document the final raw, extraction, artefact, chunk, and materialisation
  lifecycle.
- Add the full regression matrix defined below after implementation.

## Required downstream tests

### Data model and API

- Register one PRIMARY Markdown output set.
- Register one MANIFEST with multiple TABLE members and optional METADATA.
- Reject zero or multiple PRIMARY/MANIFEST members.
- Reject missing, duplicate, or non-contiguous ordinals.
- Reuse an identical complete output set without creating rows.
- Reject missing, additional, or changed retry members.
- Roll back every new artefact row when any member registration fails.
- Permit two lineage members to share one storage key.
- Reject malformed keys, mismatched hashes, unsafe logical names, invalid
  roles or media types, negative sizes, and oversized metadata.

### Chunk lineage

- Create chunk sets for two CSV members of one extraction using identical
  chunking parameters and receive distinct chunk-set identities.
- Reuse the correct artefact-aware chunk set on retry.
- Reject an artefact owned by another extraction.
- Reject METADATA as a chunk source.
- Chunk MANIFEST and TABLE members independently.
- Preserve existing null `source_artefact_id` chunk sets.
- Reject a null source for an extraction that has registered artefacts.
- Prove the composite FK prevents cross-extraction artefact references.

### Completeness and visibility

- Prevent request completion when the output set is incomplete.
- Keep incomplete sets out of searchable-chunk and request-searchability
  projections.
- Reject incomplete sets from materialisation.
- Preserve searchability for legacy CLOB-only completed requests.

### Canonical text

- Match non-ASCII `extracted_text` to exact UTF-8 PRIMARY or MANIFEST bytes.
- Remove a UTF-8 BOM before identity calculation and storage.
- Convert CRLF and bare CR to LF.
- Add a terminal LF when absent and preserve already canonical content.
- Reject artefact identity calculated from noncanonical BOM, newline, or
  encoding bytes.

### Retrieval provenance

- Return the exact source artefact, role, logical member, and ordinal.
- Return workbook, sheet, table, member source range, header rows, and hidden
  state for TABLE chunks.
- Return the narrower chunk row and cell range.
- Preserve null member provenance for legacy CLOB-backed chunks.
- Keep worksheet and table text inside the untrusted evidence boundary.

### Storage-key compatibility and security

- Resolve legacy shard locators and new logical keys to the same verified
  object.
- Prove new registrations never write legacy locators.
- Permit only the P1-05 migration path to rewrite a proven raw locator.
- Reject runtime mutation of raw locator, hash, MIME type, byte size, or source
  format.
- Verify no artefact registration package grant is added to `ORAC_PLUGIN`.
- Verify Core/API/Code controller reachability and least-privilege grants.

## P1-02 completion statement

P1-02 is complete when this design document and its linked backlog
allocations are reviewed and merged.

Completion changes documentation and backlog files only. It does not require
the artefact table, chunk-set alteration, output-set API, dual resolver,
backfill, materialisation service, or regression tests to be implemented.
