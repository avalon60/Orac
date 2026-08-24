# Knowledge Storage Maintenance

Use the Core knowledge maintenance command to reconcile Oracle metadata with
the physical managed store, inspect legacy ingestion state, backfill canonical
extraction text into managed artefacts, and migrate proven legacy raw locators.
These are operator actions; normal Liquibase deployment installs supporting
APIs but never migrates, repairs, quarantines, or deletes content automatically.

## Read-only preflight

Run a fresh preflight in every target environment before applying migration:

```bash
bin/orac-knowledge.sh preflight
bin/orac-knowledge.sh preflight --json
```

Preflight is strictly read-only. It opens the existing configured
`[knowledge].managed_root` without creating directories, probing hard links,
changing permissions, or writing temporary files. It classifies extraction
and raw-locator rows, verifies referenced bytes by hash and size, and reports
only bounded identifiers, counts, reason codes, and non-sensitive filesystem
facts. It does not emit document content, filenames, or host paths.

`READY` means the inspected candidate sets contain no blockers. `BLOCKED`
means migration must stop and the reported reason codes must be investigated.
A truncated preflight is also blocking; increase `--scan-limit` only to a
reviewed bound that covers the environment.

## Read-only operational reconciliation

Run the independent P1-09 reconciliation contract when checking whole-store
health:

```bash
bin/orac-knowledge.sh reconcile
bin/orac-knowledge.sh reconcile --json
```

Reconciliation takes one short Oracle read-only inventory, scans the physical
store, then takes a second independent Oracle read-only inventory. No Oracle
transaction remains open during filesystem work. Canonical objects are fully
hashed through non-following descriptors; temporary files are hashed only
within their independent ceiling. Root, object-directory, and temporary-
directory identities are checked again before a complete result is issued.

The report distinguishes:

- registered and verified payloads, including shared raw/artefact payloads;
- canonical, legacy, malformed, and contradictory database references;
- incomplete extraction output sets and chunk-set lineage failures;
- missing, corrupt, unsafe, malformed, unexpected, and unregistered objects;
- active versus stable stale temporary files; and
- scan ceilings or concurrent changes that prevent a safe conclusion.

`READY` means the entire bounded inventory completed, final identities were
stable, and no durable blocker was found. `BLOCKED` means a complete scan found
a durable inconsistency. `INCOMPLETE` means a limit, recent unregistered
object, replacement race, or other transient condition prevented a complete
conclusion. An incomplete scan must be retried from the beginning and never
acts as evidence that unreported entries are healthy.

A `BLOCKED` result is an operational statement about the inspected store, not
an instruction to change it and not a prerequisite for documentation or
isolated regression testing. Tests that require `READY` must build a temporary
managed root, use mocks, or run in a freshly rebuilt disposable container;
they must not make the active development store ready by deleting or changing
content.

The human and JSON forms come from the same immutable version-one report. They
contain aggregates, stable reason codes, opaque scan fingerprints, and bounded
numeric database identities only. They never contain document content,
filenames, labels, managed-root paths, storage keys, content URIs, content
hashes, service URLs, principals, scopes, or physical directory listings.

The version-one reason-code contract is grouped as follows:

- Database identity and locator: `DB_REFERENCE_KIND_INVALID`,
  `DB_REFERENCE_HASH_INVALID`, `DB_REFERENCE_SIZE_INVALID`,
  `DB_REFERENCE_MEDIA_TYPE_INVALID`, `DB_RAW_LOCATOR_CANONICAL`,
  `DB_RAW_LOCATOR_LEGACY`, `DB_RAW_LOCATOR_UNSUPPORTED`,
  `DB_ARTEFACT_STORAGE_KEY_INVALID`, `DB_ARTEFACT_ROLE_INVALID`,
  `DB_SHARED_PAYLOAD`, and `DB_CONTRADICTORY_PAYLOAD_SIZE`.
- Database lineage: `DB_ARTEFACT_OUTPUT_SET_INCOMPLETE`,
  `DB_EXTRACTION_PRIMARY_MISSING`, `DB_EXTRACTION_PRIMARY_MULTIPLE`,
  `DB_EXTRACTION_PRIMARY_HASH_MISMATCH`,
  `DB_CHUNK_SET_LEGACY_NULL_SOURCE`, `DB_CHUNK_SET_ARTEFACT_MISSING`,
  `DB_CHUNK_SET_ARTEFACT_CROSS_EXTRACTION`, and
  `DB_LINEAGE_KIND_INVALID`.
- Managed objects: `MANAGED_OBJECT_REGISTERED_VERIFIED`,
  `MANAGED_OBJECT_MISSING`, `MANAGED_OBJECT_HASH_MISMATCH`,
  `MANAGED_OBJECT_SIZE_MISMATCH`, `MANAGED_OBJECT_NOT_REGULAR`,
  `MANAGED_OBJECT_FILENAME_INVALID`, `MANAGED_OBJECT_SHARD_INVALID`,
  `MANAGED_OBJECT_LINK_COUNT_UNEXPECTED`,
  `MANAGED_OBJECT_UNREGISTERED_RECENT`, and
  `MANAGED_OBJECT_ORPHAN_CONFIRMED`.
- Layout and temporary state: `STORE_ENTRY_OWNER_INVALID`,
  `STORE_ENTRY_MODE_INVALID`, `STORE_ENTRY_CHANGED_DURING_SCAN`,
  `STORE_UNEXPECTED_DIRECTORY`, `STORE_UNEXPECTED_REGULAR_FILE`,
  `STORE_UNSUPPORTED_FILE_TYPE`, `STORE_SYMLINK_FOUND`,
  `STORE_TEMP_ACTIVE`, `STORE_TEMP_STALE`, `STORE_TEMP_NAME_UNEXPECTED`,
  `STORE_TEMP_HASH_DUPLICATE`, `STORE_ROOT_CHANGED_DURING_SCAN`,
  `STORE_CONFIG_CHANGED_DURING_SCAN`,
  `STORE_OBJECT_DIRECTORY_CHANGED_DURING_SCAN`, and
  `STORE_TEMP_DIRECTORY_CHANGED_DURING_SCAN`.
- Bounded execution and concurrency: `RECON_DATABASE_ROW_LIMIT_EXCEEDED`,
  `RECON_FILESYSTEM_ENTRY_LIMIT_EXCEEDED`,
  `RECON_HASH_BYTE_LIMIT_EXCEEDED`,
  `RECON_TEMP_HASH_FILE_LIMIT_EXCEEDED`,
  `RECON_ELAPSED_TIME_LIMIT_EXCEEDED`,
  `RECON_REPORT_BYTE_LIMIT_EXCEEDED`,
  `RECON_DATABASE_CHANGED_DURING_SCAN`,
  `RECON_FILESYSTEM_CHANGED_DURING_SCAN`,
  `RECON_CONCURRENT_CHANGE_UNRESOLVED`, and `RECON_SCAN_RETRY_REQUIRED`.

Verified, shared-payload, active-temporary, and resolved database-change
reasons are informational. Legacy locators, legacy null chunk sources,
unexpected link counts, and unexpected temporary names are warnings. Ceiling,
recent-object, identity-change, and unresolved-concurrency reasons are
incomplete. Other reason codes are durable blockers.

Safety ceilings and stale/orphan grace thresholds are configured under
`[knowledge.reconciliation]`. CLI overrides may only lower scan and report
ceilings. Full canonical-object hashing is required for `READY`; there is no
sampled or cached health mode.

Strict reconciliation writes no database audit event. Persistent execution
history, repair, quarantine, locator rewriting, content recovery, and deletion
would require separately approved write interfaces, transactions, privileges,
and audit contracts.

The two Oracle snapshots deliberately do not hold a transaction open across
filesystem work. A resolved database change can therefore be informational,
while a new reference without a corresponding enumerated object or an unstable
root/directory identity makes the result `INCOMPLETE` and retryable. A complete
scan is never inferred from a partial or raced inventory.

## Preview and apply backfill

The backfill command is a dry run unless `--apply` is supplied:

```bash
bin/orac-knowledge.sh backfill --limit 25
bin/orac-knowledge.sh backfill --apply --limit 25
```

Eligible canonical Markdown CLOBs are stored or reused through the managed
content store and registered as complete SINGLE/PRIMARY output sets. Existing
chunk-set and embedding identities are retained; the database attaches the
legacy chunk set to the PRIMARY artefact in the same transaction that
registers the output set. One extraction is committed at a time, so an
interrupted batch can be rerun safely.

Only canonical `text/markdown; charset=utf-8` extractions are backfilled.
Unsupported legacy package or spreadsheet shapes are reported rather than
invented from a Markdown compatibility CLOB.

## Preview and apply raw-locator migration

Legacy raw locators remain readable, so migration is optional and bounded:

```bash
bin/orac-knowledge.sh migrate-raw-locators --limit 25
bin/orac-knowledge.sh migrate-raw-locators --apply --limit 25
```

The only permitted rewrite is an exact, verified legacy shard locator to the
logical key for the same registered SHA-256. The command verifies the object
through the managed store immediately before the database call. Absolute,
traversal, malformed, missing, corrupt, or otherwise unsupported locators are
left unchanged.

## Exit status and recovery

- `0`: preflight or operation completed successfully, including an empty
  idempotent batch.
- `1`: an operational or per-item failure occurred.
- `2`: preflight blocked the requested migration.
- `3`: reconciliation was incomplete and must be safely retried.

Apply batches continue across independent item failures and return a bounded
result for each attempted identifier. A filesystem promotion followed by a
database failure may leave an unreferenced but valid content-addressed object;
rerunning the same item verifies and reuses it. Automated rollback never
deletes managed objects, detaches chunks, or restores legacy locators.

Promotion interruption has the same conservative boundary: the store removes
only the temporary file owned by the failing operation when it can do so
safely. A durable promoted object is retained for idempotent retry. A failed
temporary cleanup is surfaced with a stable reason and later reconciliation
may report the unchanged entry; reconciliation itself still performs no
cleanup.

The P1-05 migration preflight remains intentionally narrower than P1-09
reconciliation. A migration `READY` result does not assert that the complete
physical store has no unregistered objects or stale temporary files.

P1-06 authorised retrieval does not alter or repair managed objects. Missing,
unsafe, corrupt, oversized, or unsupported content fails with a safe retrieval
reason and an append-only decision/outcome audit. Investigate those reasons
with read-only reconciliation; do not rewrite locators or files to make a
retrieval succeed. Retrieval audit events are retained indefinitely and have
no P1-06 purge command.
