# Versioned CSV bootstrap batches

Chess installs and upgrades now apply packaged CSV batches through Liquibase,
after the administration APIs and their compilation checks. The first batch,
`2026_11_07_bootstrap`, contains the supplied 44 YouTube videos. Their six
creators combine with the five established source seeds to give eight sources
on a fresh installation. The three new sources are Yellow Rook, ChessTeacher
Games and The Chess Giant; their author and notes start blank. All publication
dates remain unknown. The Budapest Gambit and Grand Prix Attack descriptions
remain prose; descriptions never create relationships.

This is an additive release change. It adds no tables, grants, public APIs,
plugin capabilities or installation dependencies. Installation does not run
Python, read Downloads, contact YouTube or fetch any other external resource.

## Preparing a future batch

Copy the header-only `openings.csv` and `gambits.csv` templates from
`seed/batches/2026_11_07_bootstrap` into a **new** batch directory. Supply a
`videos.csv` with the documented headers, even when it has no records. Directory
names contain lowercase ASCII letters, digits and underscores. Use a new,
meaningful version identifier for every released addition.

From the repository root:

```bash
.venv/bin/python plugins/orac_chess/tools/generate_seed.py
.venv/bin/python plugins/orac_chess/tools/generate_seed.py --check
.venv/bin/python plugins/orac_chess/tools/generate_seed_acceptance.py --check
```

To validate and render a prospective batch outside the packaged directory:

```bash
.venv/bin/python plugins/orac_chess/tools/generate_seed.py \
  --batch /tmp/proposed_batch --output /tmp/proposed_batch.sql
```

Review the CSV, generated SQL and tests together, then append its include to
`db/liquibase/controllers/12_seed_batches.xml`. The generator does not silently
add new includes. Never edit a released CSV, generated SQL, changeset ID or
include path. The shared runtime template is used only when generating new
artefacts; it is not executed at installation. If the runtime changes after a
batch is released, preserve that batch's generated SQL and its generator
version rather than regenerating deployed history. Do not clear Liquibase
checksums to replace released seed data.

Each batch is a normal once-only changeset with no `runAlways` or `runOnChange`.
A successful batch stays recorded in the plugin schema's history. Later
upgrades preserve user deletions because the batch does not replay. Rollback
is deliberately `empty`: reversing an upgrade must not delete user-maintained
reference data. Correct data through the administration application or a newly
reviewed additive batch.

## CSV contract

Use UTF-8, optionally with a BOM, and standard CSV quoting. Quote cells with
commas, quotes or newlines; escape embedded quotes by doubling them. Unknown,
duplicate and missing headers, malformed quoting, record-width errors and NUL
characters fail validation. Errors identify file, physical row and column.
Names, titles, URLs, dates and identifiers are trimmed. Description, annotation
and PGN cells retain their original prose and whitespace. Empty prose becomes
Oracle null. `|` separates explicit list members and cannot be part of an
opening or gambit canonical name. List members are trimmed, exact, distinct,
nonempty canonical names; aliases are not resolved as canonical identities.

`videos.csv` requires these six columns:

```csv
Platform,Creator,Title,Video URL,Published On,Description
```

Optional columns are `External Video Id`, `Duration Seconds`, `Opening Names`
and `Gambit Names`. Platform, title and URL are required; creator is optional.
A supplied creator is created when missing, with blank author and notes.
Existing source details are preserved. Limits are platform 50, external ID 255,
URL 2048, title 500 and creator 300 characters. URLs must be absolute HTTP(S)
without credentials or whitespace. YouTube platform spelling is canonicalised
to `YouTube`; watch, youtu.be, shorts and embed URLs derive an eleven-character
ID. Duplicate `v` parameters and conflicting explicit IDs fail. Other platforms
require an explicit external ID. Duplicate platform/ID identities within a batch
fail. Dates use `YYYY-MM-DD`; durations are positive integer seconds up to
9999999999. The two relationship columns use `|` lists of exact catalogue names.

`openings.csv` uses all of these header columns:

```csv
name,opening_type,description,parent_opening_name,eco_codes,aliases,mainline_name,mainline_pgn,starting_fen,mainline_annotation
```

Name is required, at most 200 characters. Type defaults to `OPENING` and can
also be `SYSTEM`. Parent names may refer forward within the batch or to an
existing opening. Batch cycles fail generation; missing references and cycles
through existing data fail in the database and roll back the batch. ECO codes
are `|` lists from A00 through E99; aliases are `|` lists, each at most 200
characters. An existing opening's parent and other fields are preserved. Parent
assignment runs only for openings created by this batch.

`gambits.csv` uses all of these header columns:

```csv
name,description,opening_names,mainline_name,mainline_pgn,starting_fen,mainline_annotation
```

Name is required, at most 200 characters. `opening_names` is an explicit `|`
list and supports many-to-many associations.

Both catalogue files may supply one root `MAIN` line. PGN requires a mainline
name, at most 200 characters; other mainline fields without PGN fail. Starting
FEN is at most 200 characters; PGN is at most 4194304 characters. Production
`chess_variation_api` validates PGN and FEN during installation. The generator
does not replace the database validator. Branches are outside this format.
The schema permits only one root per subject: an existing root MAIN is
preserved, including its name, PGN and annotation, even when the batch proposes
a different mainline name. Existing catalogue descriptions and video fields
are also preserved. Missing explicit links are added; existing links are skipped.

## Execution and transaction boundary

The managed plugin runner reaches `pluginController.xml`, then
`12_seed_batches.xml`, then the packaged `db/schema/seed_data/chess_batch_*.sql`.
Batches run after `11_admin_compile.xml`. They create sources, catalogue
identities, parents and catalogue links, mainlines, then videos and video links.
All lookups use the published views. All writes use `chess_admin_api` or
`chess_variation_api`; no seed DML bypasses those APIs. Associations fetch the
current optimistic version and retain the returned version before continuing.

The complete batch has one outer savepoint. Any runtime error rolls back its
sources, catalogue records, mainlines, videos and links, and reports the CSV row
and operation column. The batch does not commit; Liquibase owns successful
transaction completion and history recording. Counts report inserted entities
and links, plus preserved or skipped items. CSV content is encoded as UTF-8
hex CLOB chunks, so Unicode, quotes, SQL-looking prose and SQLcl substitution
characters remain inert data. Temporary CLOBs are released on success and error.

## Verification status and isolated acceptance

Local tests cover the actual 44 records, Unicode round trips, strict quoting,
BOM/newlines, headers, identities, URL forms, dates, durations, bounds, catalogue
lists/cycles, deterministic generation and once-only controller reachability.
The schema, administration, MLE and plugin-deployment regression tests run
without modifying a database.

The following database checks are supplied **but have not been executed for
this change**. A separately authorised isolated installed Oracle environment is
required. Do not run them against the existing development database, provision
or drop a schema, or reset its history as part of this change.

1. Install the plugin using the existing managed installation path on an empty
   isolated environment, with its normal `plugin,prod` contexts and `plugin`
   label. As its `ORAC_CHESS` owner run `db/acceptance/verify_seed_install.sql`.
   It checks 44 videos, eight sources, prose, absent inferred links and one
   successful history entry through the consumer views.
2. In an isolated approved API-capable session set
   `dbms_session.set_identifier('ORAC_CHESS_SEED_ISOLATED_ACCEPTANCE')`, then run
   `db/acceptance/verify_seed_runtime.sql`. The generated harness uses the real
   batch runtime, verifies long PGN, forward parents, ECO/aliases, many-to-many
   links, preservation after replay, and atomic failure for invalid PGN, invalid
   FEN and a missing late video link. Its fixtures roll back.
3. In the isolated owner session with the same explicit identifier, run
   `db/acceptance/prepare_seed_upgrade.sql`. This intentionally commits deletion
   of one imported video. Run the managed upgrade twice, then
   `db/acceptance/verify_seed_upgrade.sql`; it requires 43 videos, the deleted
   identity absent and exactly one successful seed history entry.
4. To verify failed Liquibase history, generate a new test-only batch with a
   valid earlier row and invalid later PGN or missing video link. Add it only to
   the isolated test controller and run managed update. Verify failure, no new
   fixture rows or links through the consumer views, and zero history rows for
   that failed batch ID. Repair only the unreleased test fixture and retry;
   verify one successful history entry. Never alter a released batch to make
   this test and never retain test includes in the production controller.

SQLcl compilation, real Oracle JSON getter behaviour, database PGN/FEN
validation, fresh install, managed repeat upgrade and failed-history semantics
remain unverified until those isolated checks run. The rollback runtime harness
alone does not establish Liquibase history behaviour.

### ECO reference

Installation appends `13_eco_reference.xml`, creating `ORAC_CHESS.CHESS_ECO_CODE`
with the natural key `eco_code` (A00–E99) and a required CLOB `description`.
The 500 descriptions contain all distinct English opening names from the pinned
CC0 lichess-org/chess-openings source, sorted and separated by newlines. They
are not single canonical ECO titles. Source bytes, licence, hashes and update
policy are in `vendor/lichess-chess-openings-3ba6b20/PROVENANCE.json`.

The reviewable input projection is `seed/eco/2026_11_07/eco_codes.csv`. Run
`python plugins/orac_chess/tools/generate_eco_reference.py --check` from the
repository root to verify source hashes and generated outputs without writing.
The immutable packaged SQL inserts missing codes only, preserves existing
descriptions, uses the installer transaction and performs no network access.
Released seed migrations must not be regenerated with different source data;
review an explicit pinned update and append a new migration. Seed rollback
retains rows to protect subsequent edits; full structural rollback removes
the new table after its dependent view and grant.

`CHESS_ECO_CODE_V` exposes explicit code and description columns with SELECT
for `ORAC_APX_PUB`. Existing `CHESS_OPENING_ECO` links and game ECO values remain
compatible; no foreign key or APEX page change is introduced.

Repository checks: `.venv/bin/python -m pytest tests/test_orac_chess_eco.py`.
Live clean-install, upgrade, repeated deployment, Liquibase history and Unicode
consumer checks require an approved isolated database installation and remain
unverified by repository tests. See `db/acceptance/verify_eco_reference.sql`
for owner and consumer assertions and repeat-preservation instructions.
