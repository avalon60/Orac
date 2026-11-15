# Current Chess installation seeds

The maintained desired state lives in `seed/current.json`. Refresh it after APEX
changes with `tools/refresh_seeds.py`; the command writes one stable
`runOnChange` changeset per practical data group and describes the saved records,
counts and file path **as each file is written**. Installation reads packaged SQL
only and needs neither Python nor a network connection.

```bash
# Use an explicitly authorised existing saved connection and verify its target.
.venv/bin/python plugins/orac_chess/tools/refresh_seeds.py \
  --sqlcl-connection orac_apx_pub --expected-user ORAC_APX_PUB \
  --expected-container FREEPDB1
# Explicitly authorised read-only connection; obtain the password in the environment.
.venv/bin/python plugins/orac_chess/tools/refresh_seeds.py \
  --dsn YOUR_DSN --user YOUR_APPROVED_READER --password-env ORAC_CHESS_SEED_PASSWORD
# Reproduce reviewed portable input without connecting to a database.
.venv/bin/python plugins/orac_chess/tools/refresh_seeds.py \
  --from-snapshot plugins/orac_chess/seed/current.json
.venv/bin/python plugins/orac_chess/tools/refresh_seeds.py \
  --from-snapshot plugins/orac_chess/seed/current.json --check
```

The live exporter uses the declared `oracledb>=4.0.0,<5.0.0` Python dependency
(already used by the host). Offline replay uses the standard library only.

Saved-connection mode runs SQLcl with an argument list, verifies the expected
user/container before capture, prints that verified target, and decodes complete
hex-delimited JSON results. It requires SQLcl on PATH. Failed connections, wrong
targets or partial results leave the seed files untouched. The command selects
no default alias and never falls back to a different connection. The saved alias
above was explicitly authorised for the DEV capture; it is not an automatic
inspection-to-APEX connection fallback.

Live capture uses one read-only Oracle transaction and always rolls back and closes
it. The command selects explicit fields from the Chess reference, instructional
and association views. It excludes games, images, commentary, audit columns,
control data, host credentials and ownership baselines. The portable snapshot
contains stable keys instead of database IDs. It never discovers credentials,
adds grants, defaults to SYSTEM, deploys SQL or modifies the live database.
Connection selection remains subject to the repository's SQLcl authorisation
rules; `--dsn`/`--user` require an already authorised account.

The public APEX reader and saved-connection export mode do not read the private
catalogue identity ledger. Without
`--ledger`, capture reuses keys by exact owner/name from the previous snapshot;
a rename cannot reliably be recognised this way. Use an explicitly authorised direct
Chess owner connection with `--ledger` when capturing renamed entities: this reads
only the key, kind and entity identity columns, preserving keys across renames.
It does not export ownership, tombstones or baseline JSON. No grants are added.
Review renames carefully when capturing through public views.

`chess_content_source.sql` and `chess_eco_code.sql` use insert/update MERGEs;
editing a publisher's author/notes or an ECO description in the reviewed snapshot
updates that reference row on deployment. Publisher versions and timestamps change
only when its actual values change. These installation-owned reference values
are authoritative. Omitted rows are retained.

`chess_catalogue.sql` uses `chess_catalogue_api.apply_catalogue` rather than raw
MERGEs: it validates and resolves parents, preserves stable identities, applies
safe three-way changes to source-created rows, and protects adopted user rows,
user overrides and recorded tombstones. `chess_video.sql` uses the public video
and link APIs. It inserts missing platform/external-ID videos with captured
metadata, preserves existing video values, and adds missing opening, gambit and
variation links. It removes no links. Videos have no ownership ledger, so a
missing video can be reinserted on a later seed rerun; deliberate video deletion
must also remove it from the reviewed snapshot. Graph tombstones remain protected.

All data is validated and rendered before writing: duplicate identities, missing
references, cross-owner parents and dependency cycles refuse the refresh. JSON
text is packaged as UTF-8-safe hex chunks into CLOBs, retaining Unicode, quotes,
nulls, whitespace and descriptions larger than 32 KB. `--check` reports stale
files and exits nonzero without writing. Review the snapshot and all SQL together
before a managed plugin deployment. Rollback retains instructional data.

The controller path is `pluginController.xml` → `08_content_source.xml` and
`13_eco_reference.xml` for references, then `15_eco_seed_batches.xml` →
`18_catalogue_sync.xml` for the private API, followed by current catalogue/video
SQL. The historical bootstrap, starter, description and catalogue release files
remain unchanged on disk; their data includes are retired from active deployment.
Existing Liquibase history remains intact, and new current identities work for
both fresh installation and upgrade. No checksum clearing is required.

## Historical CSV batches

The following describes retained historical generators and provenance. New APEX
changes should use the current refresh command above rather than append another
snapshot release. Historical files are not regenerated or reintroduced into the
active controller chain.


Chess installs and upgrades now apply packaged CSV batches through Liquibase,
after the administration APIs and their compilation checks. The first batch,
`2026_11_07_bootstrap`, contains the supplied 44 YouTube videos. In that historical baseline, their six
creators combine with the five established source seeds to give eight sources
on a fresh installation. The three new sources are Yellow Rook, ChessTeacher
Games and The Chess Giant; their author and notes start blank. All publication
dates remain unknown. The Budapest Gambit and Grand Prix Attack descriptions
remain prose; descriptions never create relationships.

The later 13-Nov-2026 additive source migration supplies Gotham Chess, authored
by Levy Rozman, with blank Notes. It preserves any existing matching source row
and adds no videos. Historical baseline counts below exclude later migrations.

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
   For the historical bootstrap baseline only, it checks 44 videos, eight
   sources, prose, absent inferred links and one successful history entry through
   the consumer views; those exact counts are not current-release assertions.
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

## Starter catalogue: 10 November 2026

`2026_11_10_starter_catalogue` adds 50 openings/systems, 40 gambits, 90 root
mainlines and 100 additional named branches (60 opening branches and 40 gambit
branches). Five branches use a second parent edge. Colle System, Black Lion and
Alien Gambit are included. The subject selection is 63 mainstream, 18 historical
and 9 unusual entries (70/20/10); these are editorial categories, not strength
or safety assessments. Descriptions are original concise summaries. Complete
move orders, names and ECO references come from the pinned bundled Lichess CC0
snapshot; the batch's `PROVENANCE.json` records source file/line, source name,
move order and SHA-256 hashes. Black Lion identity also uses the
[publisher's factual description](https://www.simonandschuster.com/books/Opening-Repertoire-The-Black-Lion/Simon-Williams/9781781946282):
the Nc3/Nbd7 risky Lion move order, followed here by the CC0 4.f4 e5 continuation.
No publisher commentary is copied. The largest source families among the 100
additional branches are Sicilian Defense and Italian Game, six branches each
(6%); accepted/declined King's Gambit labels are combined for this check.

Optional `variations.csv` uses `key,owner_type,owner_name,parent_key,name,pgn,annotation`
and optional `eco_codes` (pipe-separated). `owner_type` is `OPENING` or `GAMBIT`;
`parent_key` is `owner-mainline` or another key in the same batch and owner.
PGN always starts from the initial position and contains the complete line,
including a terminal result (`*` for these instructional lines). The provenance
manifest retains the original source PGN separately from `packaged_pgn`.
The generator uses the bundled production PGN policy adapter and chess.js to
replay every supplied root and branch, enforcing the terminal result requirement,
orders forward references before their children, rejects cycles and more than
two parent edges, and derives `branch_ply` as the zero-based common-prefix
length. A continuation or truncation without a different move is not a branch.
Node.js must be available for generating/checking these batches; installation
uses only packaged SQL and the existing production validation API.

The new runtime template leaves both previous templates and their generated
SQL unchanged. `15_eco_seed_batches.xml` includes the new immutable changeset
after the ECO APIs and compilation checks. It reads approved views and writes
through administration/variation APIs in one atomic batch. Existing subject
fields, parents, roots and exact owner/name branches remain unchanged. Missing
explicit aliases, opening ECO links and opening/gambit links are added even for
existing subjects. Gambit and variation ECO selections initialise new records
only. Multiple matching branches fail the batch. If an edited parent cannot
support a missing branch, that branch and its descendants are reported and
skipped; validation runtime failures and ordinary write errors roll back the
whole batch. Direct replays add no duplicates. Normal upgrades do not replay a
recorded changeset. Rollback is deliberately empty and retains user data.

No schema, public API, query view, APEX export, navigation or existing video
record changes are required by this batch. Video consumers continue to
use the established catalogue and variation contracts.

Managed deployment to the existing DEV `FREEPDB1` installation succeeded twice
on 10 November 2026, with version `0.3.0` passing readiness: 50 openings,
40 gambits, 190 variations, 44 videos, one `EXECUTED` starter history row,
zero orphan variations and zero invalid `ORAC_CHESS` objects. APEX application
`10030` is present. These results do not cover isolated fresh installation or
direct replay. See `verification.md` for the PGN/import corrections and the
remaining page 120 Core query API declaration/grant failure.

### Isolated Oracle acceptance (not yet executed)

Use an explicitly authorised disposable database with schema `ORAC_CHESS` and
the existing runtime prerequisites; do not run these steps against a maintained
or production catalogue. Provision and install with the existing host plugin
deployment runner and contexts `plugin,prod`, label `plugin`. Run
`db/acceptance/verify_starter_catalogue.sql` as the owner after a fresh managed
install. It checks minimum catalogue counts, exactly 44 videos, two direct
replays, preservation of a user-edited Colle description/version and exactly one
Liquibase history entry, then rolls its test edits back.

For upgrade and conflict coverage in a second disposable installation:

1. Install the previous release, create a Colle System with an edited
   description and a custom MAIN line through the public APIs, then upgrade.
   Assert the field, parent, root PGN and root ECO selection are unchanged;
   missing explicit relationships are added, and incompatible branches are
   reported. Repeat the managed upgrade and confirm the history row has not
   changed and no new rows appear.
2. Before applying the starter changeset, create an owner/name branch twice
   (where the existing API permits it), then apply. Ambiguity must fail with no
   starter entities or relationships retained. Remove the ambiguity through
   the API and retry.
3. For descendant conflict coverage, inspect a second-edge branch in
   `variations.csv`. Precreate its named parent with an incompatible legal PGN,
   or edit the owner's MAIN before upgrade. Assert the missing child is skipped
   and an existing edited branch remains unchanged. An unavailable validation
   runtime or an invalid write must instead fail atomically. Restore runtime
   health before retrying.
4. Inspect Liquibase rollback SQL for this changeset: it must contain no data
   deletion. Roll back the last changeset in the disposable installation,
   verify seeded/user rows remain, and reapply; all existing rows and their
   versions must remain intact.
5. Run the existing seed/ECO/query acceptance scripts and verify the APEX
   opening, gambit and variation pages can read the supplied entries, including
   second-edge branches and direct ECO selections. Open the video page (44
   original records), confirm its existing links and navigation, and confirm no
   unexpected new video links were inferred from prose.

Isolated fresh installation, direct replay, edited-parent/conflict handling,
rollback and APEX/browser acceptance remain unverified until run on that
authorised isolated target. The successful managed DEV deployment and repository
checks do not substitute for those results.


## Known description correction — 10 November 2026

The starter batch preserves pre-existing subjects, including Vienna Game's old
blank description and test ECO selection. The later immutable
`chess_descriptions_2026_11_10.sql` changeset includes an explicit user-requested
exception: restore Vienna Game's existing subject ID to the starter metadata
(`OPENING`, canonical description, no parent, ECO `C25`). It compares those
fields before saving, so a repeat leaves an already canonical row unchanged.
Live pre-deployment comparison found its root and both named branches, including
PGN, annotations and ECO selections, already match the packaged seed; their IDs
and versions are retained. Custom/media associations are preserved.

The same correction fills only a missing/whitespace description for the known
YouTube video `0ehLrDd2pn4` using an original title-based summary. Nonempty video
text and all other subjects remain unchanged. Missing/deleted identities are
skipped. Both corrections use current row versions and public APIs atomically;
rollback retains the corrected data. Released seed files are unchanged.
`db/acceptance/verify_description_backfill.sql` provides isolated, rollback-only
reset/blank/repeat/non-target coverage; it has not been executed here.

## Incremental comprehensive catalogue sync

`tools/generate_comprehensive_catalogue.py` produces the pinned, classified source
catalogue beneath `seed/catalogue/2026_11_10_comprehensive_catalogue/`.
`tools/generate_catalogue_sync.py` converts its owner/variation records into a
reviewable `sync_payload.json` and an immutable API-mediated release SQL batch.
The semantic SHA-256 covers desired fields and sorted relationship sets; source
revision, provenance and timestamps do not change it. Correcting an existing
concept retains its stable key; explicit source-key overrides handle a move-order
correction that changes a generator-derived source identity.

The private `CHESS_CATALOGUE_ENTRY` ledger records the existing entity ID,
`CREATED`/`ADOPTED` ownership, source hash/revision, previous source desired state,
actual applied snapshot and persistent user overrides. It adds no consumer grants,
parallel opening/ECO catalogue, audit trigger or background service. Private
`CHESS_CATALOGUE_API.plan_catalogue(payload,report)` uses the same comparison and
validation path as `apply_catalogue(payload,report)`, without DML, sequence
consumption, temporary fixtures or rollback-based simulation. Reports contain
created, updated, adopted, unchanged, tombstone and ledger-change counts; set
relationship additions/removals, parent and variation-owner edge additions/removals;
skipped records, unique conflicting-record and conflict-detail counts; successful
validation-failure count zero; and explicit conflicts/deprecated keys. Fatal
validation errors retain their application error code and identify the source key.
These counters are computed per call and are not written to an audit table.

All existing untracked subjects and lines are adopted with protected scalar
fields. Previously existing relationships remain user-owned. The previously
authorised missing explicit opening ECO/alias and gambit/opening links can be
added; only newly added edges are source-managed. Existing direct gambit and
variation ECO selections remain creation-only. For records created by this
import, each field or edge changes only while its current value still matches
the previous applied value and no user override is recorded. User-added edges
remain; a user-removed managed edge is not silently re-added. Coupled variation
move/topology fields are protected together when edited. Owner changes that the
public API cannot perform also retain the whole coupled group. A coordinated
source rewrite that would temporarily invalidate retained descendants is reported
as a topology conflict: existing move/parent/owner fields remain, independent
annotation updates can proceed, and incompatible new descendants are skipped.
There is no temporary constraint relaxation or direct domain-table rewrite.
Unsupported writer fields are reported rather than claimed as applied.

An unchanged semantic source performs no domain or ledger writes, including
version-only source releases and runs after local user edits. Override decisions
are computed in memory and persisted when upstream desired state next changes.
Deleted tracked IDs
become ledger tombstones through `ON DELETE SET NULL` and are not recreated.
Dependent entries under a known deleted owner/parent and optional edges to a
known deleted endpoint are skipped and reported; unknown/malformed dependencies
still fail atomically. Disappeared upstream entries are reported as deprecated;
they are never deleted.
Apply takes the established aggregate lock, uses public save/link APIs and their
current/returned versions, writes ledger metadata only after domain validation,
and rolls all changes back to one savepoint on failure. It does not commit.
Rollback retains domain data, baselines and user overrides. New release payloads
use new immutable SQL changesets; successfully released seed SQL remains intact.

The rollback-only `db/acceptance/verify_catalogue_sync.sql` harness exercises
fresh fixture creation, adoption, strict dry runs, repeat/version-only no-ops,
source corrections, user edits, relationship overrides, tombstones, deprecation
and atomic late-error rollback through the actual API. Full structural fresh
installation still requires an isolated Oracle target; a successful upgrade of
the existing DEV schema is not evidence of a disposable fresh installation.


### Reproduce, plan and apply

From the repository root, verify the deterministic packaged artifacts:

```bash
.venv/bin/python plugins/orac_chess/tools/generate_comprehensive_catalogue.py --check
.venv/bin/python plugins/orac_chess/tools/generate_catalogue_sync.py --check
```

To prepare a read-only Oracle plan from the exact packaged SQL payload, create a
plain SQLcl wrapper in `/tmp` (the original release file is left intact):

```bash
.venv/bin/python - <<'PYTHON'
from pathlib import Path
source = Path('plugins/orac_chess/db/schema/seed_data/chess_batch_2026_11_10_comprehensive_catalogue.sql').read_text()
assert source.count('chess_catalogue_api.apply_catalogue(') == 1
block = source[source.index('declare\n'):].replace(
    'chess_catalogue_api.apply_catalogue(', 'chess_catalogue_api.plan_catalogue(', 1)
Path('/tmp/orac_chess_catalogue_plan.sql').write_text(
    'whenever sqlerror exit failure rollback\nset serveroutput on size unlimited\n'
    + block + '\nexit\n')
PYTHON
```

Run that wrapper through plain SQLcl in a fresh session as the verified Chess
owner/current schema on the authorised target. It returns JSON decisions and
conflicts without recording a Liquibase changeset. Do not run a plan wrapper as
a managed changelog. Session-only module/action progress shows `plan i/5198` or
`apply i/5198` for this release and restores the caller's prior module/action.
The payload uses UTF-8-safe bounded chunks appended to one temporary CLOB with
`LENGTH2` for supplementary characters; temporary LOBs are freed on success/error.

Apply the release through the existing managed runner after reviewing its plan:

```bash
bin/orac-plugin.sh install --bundled orac_chess
```

Controller order is existing runtime/ECO APIs and compilation → continuation
structure (`17`) → private sync ledger/API (`18`) → immutable seed batches (`15`).
A recorded release is not replayed by normal upgrades. Use a new uniquely named
release SQL changeset for future source revisions; do not rewrite a successfully
recorded release or reset its checksum to force a refresh. The private apply API
supports the new payload's incremental three-way merge without recreating IDs.

Run `verify_continuation.sql` and `verify_catalogue_sync.sql` in separate fresh
SQLcl sessions, or perform a full rollback between them: rolling back only to a
fixture savepoint can leave an active transaction handle, which the strict
read-only-plan harness correctly rejects. Full structural fresh-install evidence
still requires an isolated Oracle target. The hierarchy preview remains explicitly
limited to 2,000 rendered rows; use the default interactive Report view to search
the complete collection.
