# Administration verification record

The current DEV identity is application **10030**. Earlier deployment records
below, including the first 08-Nov-2026 layout import, describe historical states.

## Application ID correction and app 100 purge — 08-Nov-2026

The user explicitly authorised removal of application 100 and installation of
the enhanced Chess application as reserved ID 10030, including complete removal
of app-specific runtime metadata. The manifest now declares `application_id:
10030`. Both normal and read-only recovery exports default to that ID. Workspace
`ORAC`, alias `ORAC_CHESS_ADMIN`, parsing schema `ORAC_APX_PUB`, authentication,
authorisation, plugin registration and the Chess schema remain the same.

The host maintenance lock covered each mutation. Preflight verified the exact
DEV PDB, plugin registration, old receipt and application marker, no application
at 10030, and no app 100 automations. A complete SQLcl export and exact registry
snapshot were retained privately before removal. The platform
`APEX_APPLICATION_INSTALL.REMOVE_APPLICATION` API removed only app 100 after
disabling it and checking active APEX requests. The old receipt required the
existing host SYS administrative boundary: the protected receipt trigger rejects
SYSTEM updates. Through `orac_api.plugin_apex_apps_v`, the exact old receipt was
cleared first, then its installed ID, in one guarded transaction. No trigger or
database package was changed. The normal host importer then performed a fresh
10030 installation and generated a new installation receipt.

The first SYSTEM receipt-clear attempt was rejected after platform removal; its
transaction rolled back. The guarded SYS correction committed but SQL*Plus did
not emit its expected output marker. A separate host SQLcl inspection verified
the cleared registration before normal import; mutation was not blindly retried.

| Check | Verified result |
| --- | --- |
| Application, declaration, receipt and menu | All use 10030; marker matches; menu opens page 1 |
| Former app 100 | Absent globally; pages, regions, items, processes, settings and automations all zero |
| Current registry and navigation | No installed ID, declared ID, receipt application ID or list target referencing 100 |
| App 100 runtime state | Session-state and collections zero; no app 100 session callback reference |
| App 100 interactive-report preferences | 30 exact `FSP_IR_100_P…_W…` preferences backed up and removed through `APEX_UTIL.REMOVE_PREFERENCE`; zero remain |
| Enhanced ECO layout | Shared wrapping CSS on pages 11, 21 and 31; all eight disclosure regions present |
| Installed SQL/PLSQL sources | 84 parsed successfully for app 10030 without executing workflows |
| Managed readiness | `bin/orac-plugin.sh check orac_chess` passed |
| Data preservation | 500 catalogue descriptions, five opening assignments, empty gambit/variation assignments and games matched byte for byte |
| Liquibase history | All 408 rows and checksums matched byte for byte; no database deployment or checksum reset |
| Chess object validity | Zero invalid objects |

Workspace sessions are shared across applications and have no owning application
column; they were preserved. App 100 has no remaining session state, collections
or callback ownership. Historical activity logs were retained. Restricted
recovery evidence is in `/tmp/chess-id-correction-20261108/` (directory mode 0700,
files 0600); this is a private backup, not a live or deployable legacy app.

Local validation passed 99 tests across `test_orac_chess_administration.py`,
`test_orac_chess_eco.py`, `test_orac_chess_mle_runtime.py`,
`test_orac_chess_schema.py`, `test_orac_chess_seed.py` and
`test_orac_chess_validator.py`. The ECO APEX and MLE recovery generators both
passed `--check`. The new regression verifies manifest/export/recovery identity
and all eight disclosure wrappers. Earlier responsive fixture evidence below
still applies to the unchanged CSS. Authenticated app 10030 visual and workflow
checks require an authorised browser session and remain unverified.

## ECO badge layout — 08-Nov-2026

An APEX-only import used the existing host installer and receipt reconciliation
for application 100 in the ORAC workspace, parsing schema ORAC_APX_PUB. The
managed readiness check passed, the current receipt marker matched, and the
installed metadata contained the shared CSS on pages 11, 21 and 31 and the
wrapper in all eight ECO regions. The APEX source parser passed 84 sources.
Catalogue descriptions, all three direct assignment sets, games and all 408
Liquibase history entries and checksums matched before and after the import.
No database deployment was run.

A rendered local HTML fixture using the shared CSS was checked in Chrome at a
desktop width and at 320 pixels. Collapsed badges shared rows and wrapped; the
first, middle and last disclosures could be open together, with long Unicode and
unbroken text below their own summaries and no horizontal overflow. Tab, Space
and Enter worked, and closing one disclosure left the others open. This fixture
is not an authenticated Universal Theme runtime test. The existing application
session redirected to login after the import, so live appearance, editor refresh
and authenticated browser accessibility remain unverified.

## ECO DEV upgrade — 07-Nov-2026

The managed host install and a repeat install succeeded on Oracle AI Database
26ai Free 23.26.0.0.0, `FREEPDB1`. The existing application remains ID 100,
alias `ORAC_CHESS_ADMIN`, workspace `ORAC`, parsing schema `ORAC_APX_PUB`.
The host reattested the receipt during import; the current receipt identity and
application marker matched, and `bin/orac-plugin.sh check orac_chess` passed.

A pre-upgrade snapshot contained 500 catalogue descriptions, five opening ECO
assignments, no games and 376 Liquibase entries. After both installs, all
catalogue descriptions, those assignments and all 376 original checksums matched;
history had 408 rows after each install, with no checksum changes on repeat. The
new gambit and variation mapping tables remained empty after fixture rollback.
The ten new or amended ECO constraints were enabled and validated. The consumer
had SELECT without grant option on the two new mapping views and no direct grants
on their base tables. Checked ECO tables, views and API packages were valid.

The first managed attempt applied the database changes but the APEX import failed
because the new hidden items used an unsupported protection value. The export and
shared template were corrected to APEX 24.2's accepted unrestricted value;
the subsequent install and repeat both succeeded. The installed APEX source parse
check passed for 84 sources. A rollback-only DEV probe run as SYSTEM through the
public APIs checked ordinary-save mapping preservation for all three subjects,
duplicate and stale rejection, invalid variation PGN, nullable game ECO and
explicit empty clears. It rolled back its fixtures. The owner-only acceptance
scripts were not run as SYSTEM or through a changed current schema.

The existing browser tab's authenticated session had expired, so no authenticated
browser or accessibility test was performed. Fresh-schema installation, an
isolated populated upgrade, missing-catalogue game rejection, full acceptance
scripts, keyboard and narrow-screen interaction, selector empty-value handling,
filter and pagination retention, and full Unicode rendering remain unverified.
No schema rebuild, checksum reset, fresh database creation or application-ID
migration was performed.

## Earlier administration verification — 03-Nov-2026

This historical record describes the safe fallback at that date; it does not
assert that the PGN writer was available then.

## Deployed identity and objects

Verified target: `SYSTEM`, database/container `FREEPDB1`, Oracle AI Database 26ai
Free 23.26.0.0.0. Deployment used the existing managed host plugin lifecycle,
not direct owner-schema installation or a recreated baseline.

| Item | Observed result |
| --- | --- |
| Application | **100 — Orac Chess Administration** |
| Workspace / parsing schema | `ORAC` / `ORAC_APX_PUB` |
| Stable alias | `ORAC_CHESS_ADMIN` |
| URL | `http://localhost:8042/ords/r/orac/orac_chess_admin/` |
| Pages | 20 including Global Page 0 and Login 9999; all 18 business pages authorized |
| Canonical asset | `apex/orac_chess_admin.sql`, actual SQLcl export of verified app 100 |
| Export adjustments | Standard display-name prologue; host receipt value sanitized to `UNATTESTED` |
| Private data tables | 21 `CHESS_*` tables: 20 baseline plus `CHESS_ADMIN_CONTROL` |
| Optimistic versions | Eight principal-table columns, also projected through eight read views |
| Public packages | `CHESS_ADMIN_API`, `CHESS_VARIATION_API`, `CHESS_GAME_API`, `CHESS_IMAGE_API` |
| Private packages | `CHESS_ADMIN_TAPI`, `CHESS_VALIDATION_API` |
| Object grants | Exactly 20 SELECT grants on views and 4 EXECUTE grants on public packages to `ORAC_APX_PUB` |
| PUBLIC object grants | Zero |
| Invalid objects / Java objects / disabled constraints | Zero / zero / zero |
| Image listing BLOB columns | Zero |
| Persisted image limit | 10,485,760 bytes |
| Live plugin state | Enabled `Y`; installation/readiness `success`; database `already_deployed` |
| Principal entity rows after cleanup | All eight principal entities empty |

The dictionary's 16 non-null `ROW_VERSION` entries comprise eight base-table
columns and eight view projections. They are not 16 altered base tables.
Applications 1042, 1043 and 10042 retained their existing identities.

The active controller contains **257 changesets**, including the unchanged
161-changeset baseline and 96 administration changesets. DEV history contains
**332 rows** because 75 executed feasibility-spike changesets remain recorded.
No history rows or checksums were cleared. The inactive diagnostic Java chain
must not be enabled as an upgrade without a separately reviewed forward plan.

The manifest's existing `enabled: false` default is preserved. Managed installation
produced the observed live enabled state; no explicit enable command was issued.
The original live enabled state was not captured, so its preservation is not
asserted. Oracle's pre-existing user-level `INHERIT PRIVILEGES` grant to PUBLIC
was observed through `ALL_TAB_PRIVS` and preserved; it is not a Chess object grant
introduced by this release.

## Executed checks

| Check | Actual result |
| --- | --- |
| Source, deployment and export boundary tests | 13 passed |
| Inactive authoritative Java candidate corpus | 29 cases passed locally against pinned sources; included in the source tests |
| Public API acceptance as SYSTEM | `CHESS_ADMIN_ACCEPTANCE_PASSED checks=47`; exit 0; rollback complete |
| Public API acceptance as ORAC_APX_PUB | `CHESS_ADMIN_ACCEPTANCE_PASSED checks=51`; exit 0; rollback complete; approved task-scoped consumer connection |
| Privileged control companion | `CHESS_ADMIN_CONTROL_PASSED`; configuration and plugin state restored by rollback |
| Installed APEX source parsing | 74 SQL/PLSQL sources parsed successfully in app 100; no UI workflow executed |
| Two-session concurrency | Passed with measured 30.01-second lock wait; opposite reparent rejected as cycle, stale post-wait version rejected |
| Concurrency cleanup | Both precisely identified fixture rows removed through public APIs |
| Java source reproducibility | 101 generated assets verified against pinned source checksums |
| Managed upgrade and actual-export roundtrip | Repeated success targeting the same receipted application 100; no invalid objects |
| Public browser rendering | Login redirect, title, heading, username/password/remember/sign-in controls rendered without error; reconfirmed 03-Nov |

The API harness covers long CLOB preservation, optimistic versions, hierarchy
cycles, exact duplicate aliases/ECO, invalid identities and required values,
all five concept categories and all six commentary kinds, safe URLs, simultaneous
video subjects, association timestamps, restrictive deletion, unlink preservation,
PNG CRC/structure and JPEG baseline/progressive structure, malformed JPEG coding
tables, metadata-only image preservation, failed replacement rollback, controlled
image deletion and fail-closed PGN APIs. The consumer run additionally proves
base table SELECT/DML and private package execution are denied.

The separate control harness verifies a persisted smaller image limit, rejection
of nonpositive/fractional limits, restoration of the prior limit, and disabled
plugin availability rejection with rollback restoring the initial availability.
No committed fixture, configuration change, test account or credential remains.
The acceptance scripts propagate errors to a nonzero SQLcl exit; earlier failed
assertions returned exit 7 before correction. These are rollback acceptance
harnesses, not utPLSQL suite results.

The repeat-install checks exposed unchanged bodies remaining invalid after
replaceable package specifications changed. The final controller therefore
compiles the six bodies in dependency order at every managed deployment. The
final successful roundtrip and dictionary checks include that correction.

## Historical Java PGN gate

The source-only Oracle JVM spike failed with **ORA-29536**, encountering the
Java interface `default` method in pinned Commons Lang 3.12.0
`org/apache/commons/lang3/function/FailableBiConsumer.java` (generated source
parser line 43). The runtime Java version did not establish source-DDL parser
compatibility. SQLcl annotation parsing was first handled with generated static
CLOB source-DDL blocks; the subsequent Oracle source parser incompatibility
remained a genuine blocker.

Pinned chesslib 1.3.6 commit
`c270a79e9a201357581de9a5d0360275f535b4b8` and Commons Lang 3.12.0 commit
`105a350b154eac7c3f3a6bac94ec2cfb0fbe232b`, upstream licenses, SHA256 checksums,
the strict candidate adapter and regression corpus are retained. Diagnostic
loading assets are under `db/diagnostics`, outside the active controller.
Exactly 74 temporary source units and their 98 derived classes were inventoried
and removed; the final dictionary contains zero Java objects.

At that recorded deployment, games and variations were visibly read-only and
their public save/delete APIs raised `-20020` before mutation. No alternative service, browser-only validator,
homegrown chess engine, JAR loader or broad Java permissions were substituted.
The local candidate corpus is not evidence of Oracle-side PGN validation.

## Remaining verification and limits

- **Authenticated browser workflows were not run.** No authorized account/session
  or credentials were available. Login rendering and metadata/source parsing do
  not prove save/cancel/dialog/LOV workflows or authorized image delivery in a
  browser. No new accounts or credentials were created.
- **Fresh isolated runtime installation was not run.** No approved empty target
  schema/container and provisioning route were available. Static controller
  reachability and successful baseline upgrades do not substitute for that test.
- **utPLSQL integration/execution was not completed.** The framework is absent;
  separate `UTPLSQL_DEV` provisioning/topology confirmation remains pending.
  It was neither installed nor bundled by this plugin.
- Image validation is bounded format/structure validation with a 16-megapixel
  limit, not full PNG deflate/JPEG entropy or pixel decoding. Safe MIME,
  sanitized disposition, `nosniff` and private/no-store delivery are retained.
- All maintenance currently takes the common control-row lock. This serializes
  writes deliberately and limits write throughput in exchange for simple,
  verified hierarchy correctness.
- Authenticated fill-empty-header interaction, rendering and modal workflow
  remain unverified. Production API, concurrency and withdrawal/reapplication
  runtime results are recorded below.

No LOGGER instrumentation, ingestion, MCP, transcript/YouTube API, AI, engine,
full-study framework or unrelated core changes were introduced. No git commit
was made; unrelated pre-existing workspace changes were preserved.

## MLE integration runtime, 07-Nov-2026

Duration/date UX changes were subsequently deployed through the host importer
to application 100. Duration entry and display use MM:SS or H:MM:SS while the
API/storage and report sorting retain numeric seconds. Installed metadata
confirmed DD-Mon-YYYY masks on both date pickers and both date report columns.
Twenty-five focused Chess tests passed. Source-derived Oracle assertions passed
for nullable/valid/invalid durations, numeric limits, formatting round trips,
leap-day/date rejection and English months under a French-language session.
The enhanced installed-source check passed all 75 sources after deployment.
These checks do not substitute for a new authenticated rendered-browser test.

Subsequent video UI changes were imported through the host receipt path into
application 100: URL sequence 11 precedes editable External Video ID sequence
12; the YouTube change action is bound to URL and Platform; the report URL link
has `target="_blank" rel="noopener noreferrer"`. Installed metadata confirmed
these settings. Thirteen administration tests passed, including execution of
the exported JavaScript against supported URLs, invalid/spoofed URLs and manual
ID preservation. Recovery generation and whitespace checks passed. Browser
verification stopped at sign-in after the import reset the existing session;
rendered interaction and responsive layout are not claimed here. Planning and
implementation used the balanced profile's gpt-6.1-sol/low roles; independent
review remained disabled and no separate tester was configured.

Video Platform was subsequently changed to a static LOV at the stakeholder's
request. Host import retained application 100; installed metadata confirmed
`P41_PLATFORM` is a Select List with `STATIC:YouTube;YouTube` and default
`YouTube`. Ten administration tests and the recovery generator check passed.
This metadata check does not claim a new authenticated browser test.

Final combined local regression run after the browser-discovered fixes:
82 tests and 79 subtests passed (Chess plus host provisioning).

The bounded proof passed twice against Oracle with 44 corpus/boundary cases and
CLOB transport above 64K; see [MLE feasibility](mle-feasibility.md). The stakeholder
then approved the scoped DEV upgrade, acceptance, concurrency and recovery work.
The production integration was installed through the managed lifecycle.

| Check | Observed result |
| --- | --- |
| Managed upgrade | Passed after correcting plugin-local Python imports and APEX export arguments |
| Private MLE objects | All 7 VALID; owner provisioning reconciled narrow CREATE MLE |
| Liquibase history | 332 before integration, 340 after; baseline/diagnostic history retained |
| Application identity | Installed 100, alias ORAC_CHESS_ADMIN, receipt 100; no installed 10030 |
| Production facade corpus | 45 cases passed, including null/Unicode, 4Mi and depth64/65 |
| ORAC_APX_PUB public API acceptance | 60 checks passed; rollback fixtures; private/base DML denial included |
| Unavailable-runtime check | Passed with MLE disabled only in its consumer session; -20020 and no game mutation |
| Installed APEX source parse | 75 sources passed for application 100 |
| Parent/child concurrency | Passed, observed lock wait 34.09 seconds |
| Competing-root concurrency | Passed, observed lock wait 33.45 seconds |
| Concurrency cleanup | Reserved fixtures remaining 0 |
| Read-only recovery import | Passed, application 100 retained and edit buttons 0 |
| Runtime withdrawal | Passed, 7 private MLE objects removed, invalid objects 0, history 340 retained |
| Withdrawn write refusal | Passed, public PGN writer failed closed |
| Managed reapplication | Passed through ordinary runAlways canonical runtime/writer path |

These results were reported by the coordinating agent from approved runtime
execution. This record does not claim an isolated fresh install or authenticated
browser workflow. Post-reapplication production corpus 45 and consumer API 60 checks passed
again. Canonical export reinstallation and managed readiness passed. The latest UI
corrections were then installed successfully, and the strengthened source checker
passed all 75 sources.

The source export was replaced from the actual application 100 SQLcl export using
`-expOriginalIds` on 07-Nov-2026. Its original default remains 10030, while host
receipt/import selection retains installed 100. The standard display-name prologue
is preserved and the packaged ORAC_INSTALL_RECEIPT is reset to UNATTESTED.
Recovery export was regenerated from that canonical export.

Local verification: 20 Chess Python tests passed, including production typed CLOB
bridge boundaries. The 39-case portable MLE corpus plus header/size/depth boundaries
passed. Runtime/acceptance/recovery generators passed their deterministic
`--check` modes. The configured balanced profile uses gpt-6.1-sol/low planning
and implementation; independent reviewer is disabled and no separate tester is
configured. No independent review result is claimed.

See [runtime deployment scope](mle-deployment-scope.md) for exact commands,
consumer connection exception, committed fixture names and recovery procedure.
The scripts remain acceptance assets, not utPLSQL suite execution.

Fresh disposable target, authenticated browser session and utPLSQL provisioning
remain outstanding inputs. Authenticated browser testing exposed and corrected the welcome HTML/output
setting and stale copy, an invalid game-load SELECT INTO date target, and missing
PL/SQL language declarations on both dynamic hierarchy regions. The corrected
managed import passed. Reimport reset the browser session; full authenticated
workflow/layout testing remains pending. Source checks alone do not prove it. No new
accounts or credentials were created. No application-ID migration was performed.


The latest corrected application 100 was exported again to the canonical asset
on 07-Nov-2026, retaining original IDs/default 10030, display-name prologue and
packaged receipt UNATTESTED. Recovery was regenerated and all three generator
checks passed. The source-check harness now executes PL/SQL only inside an
`IF FALSE` wrapper with null session-state binds, forcing compilation while
preventing the original workflow statements from running. This addresses the
parse-only blind spot exposed by the game-load target error; it remains distinct
from authenticated browser acceptance.

## Content sources — deployment verification 07-Nov-2026

The requested Content Source feature was deployed through the managed DEV
lifecycle in FREEPDB1. Application 100 and receipt 100 remain installed.
Historical observations above retain their recorded dates and counts.

The current source adds one private table, one PK, two check constraints, two
indexes, one nullable restrictive video FK, one read view and one SELECT grant.
It extends the existing public admin package and private TAPI; it introduces no
consumer table DML or private-package grants. Five missing seed identities and
all distinct existing video creator names are inserted without overwriting edits.

Repeatable acceptance assets are
`db/acceptance/verify_content_source_structure.sql` in the approved DEV admin
session, then `db/acceptance/verify_content_source.sql` as `ORAC_APX_PUB`. The first
script reads metadata and checks the natural PK, nonunique video index, validated
restrictive FK, nullable creator, CLOB notes and least privileges. The second uses
only public APIs and read views, rolls all fixtures back, and checks long notes,
versioned CRUD, duplicate/blank/stale rejection, two videos per creator, unknown
and null creator handling, referenced rename/delete rejection, unreferenced
rename, failed-operation rollback, unchanged video versions and denied private
TAPI/table DML. It propagates failures to SQLcl.

Managed Liquibase execution, readiness and the structure companion passed.
The consumer API acceptance passed 18 checks with fixtures rolled back. The
repeat-seed check passed and restored the original author, notes and version by
rollback. All five supplied seed rows were verified exactly; both existing
ChessVibes videos remain linked without rewriting their values. No test source
rows or invalid schema objects remain.

Installed metadata confirms pages 110/111, the Popup LOV, CREATOR as return and
primary display column, and visible/searchable CREATOR and AUTHOR columns.
The installed-source compilation check passed 79 sources; the existing consumer
administration regression passed 60 checks. The first APEX import exposed a
String-versus-Boolean required-item argument; correcting it to `true` allowed
the managed retry to complete.

Fresh isolated installation and authenticated report/form/creator selector
browser workflows remain unverified. Existing baseline
`verify_structure.sql` describes the historical pre-administration installation;
use the new structure companion for this forward migration.

Local validation: all 30 focused Chess schema, administration, MLE runtime and
validator tests passed. The schema payload validator resolves every source SQL
file through the controller, checks unique changeset identities and rollback
presence, and confirms the updated abbreviation register. `git diff --check`
passed. These source checks do not replace Oracle execution or browser evidence.

The optional `db/acceptance/verify_content_source_seed_repeat.sql` uses a dedicated
approved DEV admin session to edit ChessVibes Author/Notes through the public API,
include the actual production seed SQL, and assert the edits and row version
survive. It rolls the transaction back to restore the original values and never
renames the source or writes videos. Run it only after deployment; it has not
been executed as part of local source validation. The historical
`verify_structure.sql` is explicitly labelled baseline-only and is excluded from
current-release installation commands.

### ECO reference

Run `python plugins/orac_chess/tools/generate_eco_reference.py --check` and
`.venv/bin/python -m pytest tests/test_orac_chess_eco.py` from the repository root.
These verify pinned source hashes, all 500 codes, every source name, Unicode,
malformed source rejection, reproducibility, host import checks and controller
reachability. They do not connect to a database.

For an approved isolated installation, run `db/acceptance/verify_eco_reference.sql`
as `ORAC_CHESS` after clean installation, upgrade and repeated deployment. The
script includes consumer access, user-edit preservation and failure-atomicity
rehearsal instructions. Live installation, Liquibase history and Unicode consumer
behaviour remain unverified until those checks are performed.
