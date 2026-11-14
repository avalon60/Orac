# Administration verification record

The current DEV identity is application **10030**. Earlier deployment records
below, including the first 08-Nov-2026 layout import, describe historical states.

## Opening detail selector — 13-Nov-2026

Both packaged exports rename the detail region to **Opening Synopsis** and add
one native **View** selector for Opening Synopsis, ECO Codes and Opening Gambit.
Opening Synopsis has the first display sequence; Show All and remembered
selection are disabled. Existing form items, save/delete/cancel actions and
gambit link/unlink controls retain their region connections.

Local verification: 46 focused Opening/Variation selector, administration, ECO
and APEX callback tests passed. ECO and recovery generator checks and scoped
`git diff --check` passed. Only the page 11 disclosure gains selector membership
through the shared ECO template. No database or APEX import was performed.
Authenticated desktop and narrow-screen verification remains pending after an
authorised import: check the default tab, switch all three views, confirm ECO
disclosure and gambit report actions, and save an Opening edit.

## Parent opening dropdown — 10-Nov-2026

DEV application 10030, page 11 now excludes the current opening and all its
descendants from `P11_PARENT_OPENING_ID`. Valid ancestors and unrelated openings
remain selectable; a new opening lists all openings and `- None -` remains.
Both packaged exports carry the same filter. The live page was exported before
importing a copy with only this LOV changed; unrelated pending repository changes
were not deployed. Backup: `/tmp/chess-parent-lov-20261110/opening-page-before.sql`.

Host SQLcl verified SYSTEM / FREEPDB1 and the ORAC workspace, ORAC_APX_PUB owner
and ORAC_CHESS_ADMIN alias before import. Installed metadata matches the filter.
Read-only Oracle fixtures against the installed SQL passed self/descendant,
valid-parent and null-ID cases. All 26 administration tests passed. Refreshing
the authenticated Vienna Game form confirmed its own name disappeared from the
parent dropdown, leaving `- None -` for the current catalogue.

## Governed reference query source — 08-Nov-2026

Version 0.3.0 adds disabled query source assets, narrow projections and READ grants,
a shared Core service and Query Chess page 120. Read-only DEV inspection used
CSV environment `dev` / connection `orac`; the verified session was ORAC in
FREEPDB1, current schema ORAC. No CHESS_QUERY objects were visible. Live contents,
provenance/classification, effective executor grants/dependencies, Oracle fresh
install/upgrade/rollback and authenticated APEX workflows remain unverified.
No schema/application deployment or enablement was performed. See
[reference querying](reference-query.md) and the [Core release gate](../../../docs/relational-query.md).

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


### Subject video workflow source phase — 08-Nov-2026

The canonical application `10030` export and generated recovery export now share
the Related videos workflow on Opening `11` and Gambit `21`, and the native
Video `41` modal reused by Videos `40`. Source checks execute the exported parent
JavaScript with mocked APEX APIs: exact-version adoption, stale-result rejection,
identity/token mismatch rejection, metadata-only refresh, unsaved-field retention,
and a browser environment without `crypto.randomUUID`. Checks also cover signed
origin items, numeric AJAX identities, safe outbound URLs, excluded existing
links, modal cancellation/closure and baseline/ECO public-contract parity.

`create_video_for_subject` and `set_subject_video_link` are additive public API
operations delegated to the private TAPI. Each composed mutation has a distinct
outer savepoint, uses the existing control lock and save/link routines, and leaves
commit ownership with its caller. Existing link routines increment video and
subject versions exactly once. No tables or grants were added. Deployment remains
host plugin runner → `db/liquibase/pluginController.xml`. The corrected dependency
order is `13_eco_reference.xml` → `10_admin_api.xml` (baseline specs/bodies) →
`14_eco_relationships.xml` (ECO replacement specs/bodies and ECO compile) →
`11_admin_compile.xml` → `12_seed_batches.xml` → `15_eco_seed_batches.xml`.
The ECO seed controller is included once at the root, after bootstrap seeds;
final ECO contracts are restored before the shared compilation pass. These are replaceable
`runOnChange` package changes with their existing rollback declarations.

`db/acceptance/verify_subject_videos.sql` is a **test/support artifact**, also
included by `verify_admin_api.sql`. On an approved DEV connection it exercises
both subjects, atomic creation, duplicate video/link rejection, missing records
and links, invalid subject kind, stale video/subject versions, no orphan videos,
exact version increments, metadata-only subject-version stability, shared-video
retention and caller rollback. A commit inside an API invalidates the caller's
savepoint and fails the harness. At the end of the source phase, this new SQL
harness had not been executed; the subsequent DEV results are recorded below.

Local verification for this source change: the four focused Chess administration,
ECO, schema and seed modules passed **100 tests**. ECO generation and regenerated
MLE recovery reproducibility checks, plus `git diff --check`, passed. At that
source-phase checkpoint, live package compilation, installed APEX source parsing,
fresh installation, upgrade, Liquibase execution/history, rollback SQL execution
and authenticated desktop/narrow browser workflows were unverified. Subsequent
DEV deployment evidence follows; browser and isolated fresh-install evidence
remain outstanding. The link-existing search
currently filters the available video choices in the browser; assess a paginated
server search if the catalogue grows substantially.


### Subject video workflow DEV deployment — 08-Nov-2026

The approved target was verified as `SYSTEM` in `FREEPDB1`. The first managed
`bin/orac-plugin.sh install --bundled orac_chess` attempt failed at controller
`11_admin_compile.xml`: replacing the installed ECO TAPI specification with the
baseline specification temporarily left the unchanged ECO variation body referring
to missing `SAVE_VARIATION_WITH_ECO`. The dependency order was corrected as shown
above, retaining the ECO compile inside controller `14` and moving controller
`15` to one root include after bootstrap. No changeset history or checksum bypass
was used. The managed retry and a repeat installation both succeeded;
`bin/orac-plugin.sh check orac_chess` also passed.

Installed APEX metadata confirmed application `10030`, workspace `ORAC`, alias
`ORAC_CHESS_ADMIN`, parsing schema `ORAC_APX_PUB`, Related videos regions on pages
`11` and `21`, and page `41` as a Modal Dialog. Host registration reported success,
database `already_deployed`, readiness success and enabled `Y`. The installed
receipt and declared application ID both matched `10030`; host readiness verified
the receipt.

`verify_subject_videos.sql` passed twice with its fixtures rolled back.
`verify_apex_sources.sql` passed twice, parsing **91** installed sources on each
run. Chess had zero invalid objects and zero `DBA_ERRORS` rows. Before/after
snapshots matched: **1 opening, 0 gambits, 44 videos, 0 video-opening links and
0 video-gambit links**. Liquibase retained the same **408 history keys**, with no
added or removed keys and no history resets. The only checksum changes were the
expected eight `runOnChange` administration API/TAPI specification/body assets
across baseline and ECO variants.

Private backup, count/history snapshots and deployment logs are retained in
`/tmp/chess-video-import-20261108` with directory mode `700`. These DEV results
verify the managed upgrade/repeat path and installed source/API acceptance.
An isolated clean fresh installation and authenticated browser workflows at
desktop and narrow widths remain unverified, including rendered layout,
accessibility, dialog interactions and preservation of unsaved fields in the
actual browser.

## Video title links, 08-Nov-2026

Imported the canonical export through the host receipt-checked APEX importer
into DEV `FREEPDB1`, workspace `ORAC`, application `10030`. Installed page 40
metadata confirms `TITLE` uses `#VIDEO_URL#`, link text `#TITLE#`, and
`target="_blank" rel="noopener noreferrer"`. The 22 administration tests and
recovery generation check passed. Rendered browser interaction was not checked.

The initial full lifecycle attempt stopped at the pre-ECO compilation assertion:
its earlier administration scripts had replaced ECO API contracts/bodies before
the later ECO controller could restore them. Restored the canonical ECO TAPI and
administration API specifications/bodies and variation API body, then recompiled
the administration bodies. Final owner metadata shows no invalid Chess objects or
compilation errors; the schema-qualified PGN validation smoke returned no error.
The host plugin status remains enabled with installation/readiness `success`.
The repeat-install ordering defect remains unresolved; use the host APEX importer
for this UI-only update rather than repeating full database deployment.

## Related video search source fix, 08-Nov-2026

The Opening and Gambit search handlers now use the Related videos region element
to find available choices. The dynamic content region has no widget, so the
previous handler failed before updating visibility. The recovery export was
regenerated from the canonical export.

The regression executes each exported handler after decoding both SQL string
layers, with a null region widget. It reproduces the previous error and passes
with the correction, covering case-insensitive title, creator and platform
substrings, no matches, clearing the search, replacement rows after a region
refresh, and preservation of linked rows. All **26 administration tests** passed;
ECO and recovery generator `--check` runs and `git diff --check` passed. A
repository-wide search found the corrected handlers only in the canonical and
generated recovery exports, with no remaining old handler.

The installed DEV app was backed up to `/tmp/chess-before-search-fix/f10030.sql`.
The host receipt-checked APEX-only importer then applied the same two handler
corrections to that fresh export, preserving other installed app settings. Import
completed for application `10030` in `FREEPDB1`. SQLcl metadata confirms corrected
handlers on both pages 11 and 21 and no invalid `ORAC_CHESS` objects. No database
controllers or schema changes were run. The import reset the existing browser
session; authenticated browser acceptance is pending sign-in. Other workflow
documentation remains accurate because existing search behaviour is restored.


## Related video submission race protection, 08-Nov-2026

Observed facts: the exported Opening and Gambit Link controls start asynchronous
`SUBJECT_VIDEO` requests. Previously, page submission was allowed before their
responses updated the subject version. The saved DEV export at
`/tmp/chess-before-search-fix/f10030.sql` contains the same callback and version
adoption path. Save only processes subject metadata and ECO associations; typing
in the video search does not itself link a video. The existing API acceptance
harness checks link/unlink versions and caller rollback, rather than browser
request ordering or cross-request persistence.

Derived conclusion: Save could submit the older observed version while a video
mutation was pending. Both pages now cancel page submission during that request
and reject overlapping video actions. Success payloads must contain a dialog URL
or a positive mutation version, with no error, before they are used. Request
completion releases the submission barrier after success or failure. API
transaction ownership and callback commit behaviour are unchanged.

The exported JavaScript regression exercises both pages with a delayed response:
submission is rejected before completion and allowed after adopting the returned
version. It also covers overlapping actions, error payloads, network errors,
unchanged unsaved fields and stale dialog responses. The generated recovery export
contains the same protection.

Unverified hypothesis: request ordering may explain the reported association
missing after Save/reopen. No authenticated reproduction, Link response trace or
persisted before/after state has yet established the cause of that report. The
source protection has not been imported or checked in the live browser. Required
acceptance remains: link an existing video, Save and reopen each subject type;
repeat with immediate Save during a delayed request and verify the association
from a subsequent request, including rendered desktop and narrow layouts.

Authenticated browser acceptance completed on 08-Nov-2026 in a separate Chrome
verification tab. On Gambit 124 (Queen's Gambit) and Opening 83 (Vienna Game),
`iCeLaNdIc` showed exactly three matching available videos. A nonmatching query
hid every available choice while the existing linked video stayed visible.
Clearing restored all 43 available choices on each page. Browser error logs were
empty after the checks. Desktop rendering of the filtered Opening region was
visually inspected. No records or video associations were changed. Narrow-screen
layout and live dialog/association refresh were not exercised; replacement-row
filtering remains covered by the executable regression.

## Starter catalogue repository checks — 10 November 2026

The immutable `2026_11_10_starter_catalogue` batch supplies 50 openings/systems,
40 gambits, 90 root mainlines and 100 additional named branches. The generator
validates complete initial-position PGN with bundled chess.js, reference ECO
codes, topological ownership, genuine divergence and a maximum of two parent
edges. Original released SQL and both previous runtime templates remain byte
identical. Source-level checks verify the bundled TSV hashes and every selected
source record against the per-entry provenance manifest.

The focused seed, starter-catalogue, ECO, administration and validator checks are covered
by `tests/test_orac_chess_seed.py`, `tests/test_orac_chess_starter_catalogue.py`,
`tests/test_orac_chess_eco.py`, `tests/test_orac_chess_administration.py` and
`tests/test_orac_chess_validator.py`.
The initial focused run passed 103 tests; after the terminal-result correction
the same focused suites passed 106 tests.
`tools/generate_seed.py --check` verifies both packaged batches and controller
registration. In a combined run including the schema suite, 110 tests passed
and two existing manifest assertions failed because the working tree already
declares `orac_chess.query`; those assertions still expect no capabilities.
This catalogue change does not modify that manifest or those assertions.

The authorised isolated-target acceptance route is documented in
`bootstrap-seeds.md`, with an executable replay/edit/history check at
`db/acceptance/verify_starter_catalogue.sql`. Fresh installation, direct replay,
edited-parent/conflict handling, rollback and browser/consumer acceptance remain
unverified. The managed DEV deployment evidence below covers the existing
installation only.


The first authorised DEV reinstall attempt exposed a packaging defect: source
move sequences lacked the terminal PGN result required by the database
validator. Before any successful history entry, the undeployed starter batch
was corrected to append `*` to all 190 instructional lines. Source PGN remains
verbatim in provenance; `packaged_pgn` records the complete input. Offline
validation now uses the bundled production PGN policy adapter (backed by
chess.js), with regression coverage rejecting missing terminal results in
opening roots, gambit roots and branches. This correction does not alter the
released bootstrap batch or either historical runtime template.


## Starter catalogue DEV deployment — 10 November 2026

Two consecutive managed `bin/orac-plugin.sh install --bundled orac_chess` runs
succeeded against DEV `FREEPDB1`; plugin version `0.3.0` passed readiness.
Post-install metadata showed 50 openings, 40 gambits, 190 variations and the
original 44 videos. The starter changeset has one `EXECUTED` history row;
there were zero orphan variations and zero invalid `ORAC_CHESS` objects.
APEX application `10030` was present. The second managed run succeeded without
replaying the recorded starter changeset. The successfully installed starter
SQL has not been changed since that deployment.

The import also required a narrow correction to the existing page 120 query
callbacks: `CHESS_QUERY_SUBMIT` and `CHESS_QUERY_READ` now use `ON_DEMAND` in
both canonical and recovery exports. The live APEX 24.2 process-point constraint
accepts `ON_DEMAND` and does not accept `AJAX_CALLBACK`. Callback, administration
and ECO regressions passed 38 tests; query logic and authorisation are unchanged.

A separate installed-source check, `verify_apex_sources`, still fails for page
120 `CHESS_QUERY_SUBMIT` with `PLS-00201: ORAC_CODE.RELATIONAL_QUERY_API must be
declared`. The separate Core query feature is not deployed or lacks the needed
grant in this target. The successful managed install/readiness result does not
establish that this query page works. Core query deployment or grant correction
is outside the starter catalogue change and was not performed here.

These managed reinstalls do not establish isolated fresh-install, direct replay,
user-edit/conflict, rollback or rendered browser acceptance. Those checks remain
unverified, including end-to-end APEX/query consumer behaviour.

### Variations view selector — 10-Nov-2026

Managed installation of Chess 0.3.0 succeeded and passed readiness checks in
DEV FREEPDB1, application 10030. Installed page 30 metadata confirms the native
View selector at sequence 5, Report at 10 and Variations Hierarchy at 20.
Authenticated desktop browser verification confirmed Report is selected after
page load and reload, switching to Variations Hierarchy hides the report, and
switching back restores the interactive report. No Show All tab is offered.
Narrow viewport verification was not performed. The 40 focused selector,
administration, ECO and callback tests passed, as did recovery generation
verification and `git diff --check`.

### Description completeness and Vienna reset — 10-Nov-2026

The managed Chess 0.3.0 installation succeeded and passed readiness checks on
DEV FREEPDB1. The additive description correction restored Vienna Game's
existing subject ID 83 to the packaged OPENING classification, canonical
description, no parent and exactly C25, as explicitly requested to replace its
earlier test metadata. Its three already canonical move lines were untouched.
The one blank ChessVibes video description was filled using its stable identity.
Post-install owner queries confirmed zero missing/whitespace descriptions among
50 openings, 40 gambits and 44 videos, and zero missing annotations among 190
variations. Before/after description checksums and aggregate row versions for
all non-target openings, all gambits, all variations and all non-target videos
matched. Vienna's version advanced from 22 to 23. The 72 focused description,
catalogue and seed tests, both released seed generation checks and whitespace
checks passed. Isolated correction acceptance and browser inspection were not
performed during this deployment.


## Continuation support repository checks — 10 November 2026

Approved additive `CONTINUATION` edges use the complete-parent UCI and position
prefix, a strictly longer legal child PGN and `branch_ply` equal to the parent's
half-move count. Existing `MAIN`/`ALTERNATIVE` behaviour is retained. Immediate
saves and retained-descendant checks route through the same private MLE-backed
validation operation; baseline and ECO TAPI paths, Java diagnostics, recovery
withdrawal and APEX line-kind help/LOV are included in the change.

The portable Node corpus passes 47 cases, including valid continuation and
wrong-prefix, equal, shorter, wrong/fractional/negative-ply and own-FEN rejection.
The original released branch constraint and table creation SQL are unchanged;
new controller `17_continuation.xml` runs after API compilation and before seed
controllers. Separate once-only DDL changesets add the wider validated check
before retiring the narrow check, and retain the additive support on rollback.
These continuation-specific checks are separate from the approved private
catalogue sync ledger and release application described below.

`db/acceptance/verify_continuation.sql` supplies rollback-only owner/child/FEN,
grandchild, alternative, ancestor-edit and atomicity acceptance through the public
writers. This script, Oracle compilation/migration, concurrency and rendered APEX
continuation maintenance have not been executed for this change. The comprehensive
catalogue sync uses its separately approved reconciliation design.


## Comprehensive catalogue runtime acceptance — 11 November 2026

The approved private catalogue ledger/API installed validly in DEV `FREEPDB1`.
Live rollback-only continuation acceptance passed, including new-child owner,
PGN/edge/FEN rejection and retained-descendant rollback on ancestor updates.
The full sync fixture harness passed actual creation/adoption, strict dry-run
transaction/sequence preservation, unchanged and version-only repeats, unchanged
source after local edits, independent field updates, user overrides, untracked
user relationships/parents, tombstones and dependent skips, deprecation, atomic
late failure and coordinated parent/child topology conflict handling. These
fixtures were rolled back; they do not certify a separate structural fresh install.

The complete read-only release plan completed in 11 minutes 54 seconds and
reported 5,018 creations, 55 existing relationship updates, 180 adoptions,
125 unchanged entries, 5,198 ledger entries and 71 protected-field/relationship
conflicts, with no deprecated keys. It performed no catalogue DML. The 5,198
payload entries are 128 openings, 612 gambits and 4,458 variation references;
100 original curated branches remain outside the payload and are preserved,
so the projected installed variation total is 4,558.

An initial full apply was cancelled after performance evidence showed repeated
whole-owner-tree validation for every inserted leaf. Its transaction rolled back:
metadata checks confirmed the original 50 openings, 40 gambits and 190 variations,
zero catalogue-ledger rows and no comprehensive release history row. Both TAPI
paths now capture insert/update intent before ID allocation. New leaves retain
all authoritative local checks and immediate parent foreign keys under the
aggregate lock; only the redundant scan of unchanged siblings is omitted.
Existing-node updates retain whole-tree validation. Both live acceptance harnesses
passed again after this invariant-preserving optimisation.

Final managed release completion, baseline preservation, full repeat results and
APEX browser evidence are recorded after the live application finishes. Until
then the plan counts above are projected, not installed counts. The source
coverage report separately records shorter-prefix omissions and the deferred
Lion's Jaw mapping; mapped source rows are not a claim that every row became a
new branch. The former 2,000-row hierarchy preview limit remains visible and the
interactive Report is the complete search route.


### Query Chess layout deployment — 12-Nov-2026

Two consecutive managed `bin/orac-plugin.sh install --bundled orac_chess`
runs succeeded on DEV FREEPDB1, with readiness passing. The separate
`bin/orac-plugin.sh check orac_chess` also passed. Installed APEX metadata
confirms application 10030, parsing schema ORAC_APX_PUB, page 120 native
P120_QUESTION textarea and ASK_CHESS button with Defined by Dynamic Action.

The installed-source acceptance check still fails on CHESS_QUERY_SUBMIT with
PLS-00201 for ORAC_CODE.RELATIONAL_QUERY_API. Read-only SYSTEM metadata confirms
neither RELATIONAL_QUERY_API nor RELATIONAL_QUERY_WORKER_API exists in
ORAC_CODE; the APEX API grant is absent too. Thus the layout deployment does
not make querying operational. Core query deployment, live dataset review and
enablement were not performed by this UI deployment.

Browser navigation reached the application's login page after import. Rendered
layout and authenticated query acceptance therefore remain unverified pending
fresh authentication. Local callback and administration regression evidence
remains separate from this live installation evidence.

### Query Core deployment and prose implementation — 12-Nov-2026

The user-authorised query-only DEV release applied 34 new Core changesets
through the existing deployment runner filtered by `relational_query`. The
canonical controller paths and changeset identities were retained; unrelated
pending Core migrations were not applied. Both ORAC_CODE query package
specifications/bodies are VALID. The APEX query API is granted to ORAC_APX_PUB;
the worker API is granted to normal ORAC. Installed APEX source validation now
passes 92 sources, resolving the previously recorded missing-API failure.

Two managed Chess installation runs succeeded. All 12 query projections are
VALID. The acceptance PL/SQL executed as ORAC_PLUGIN verifies all 12 READ
grants and the excluded-column boundary. SYSTEM's ALL_TAB_PRIVS returned zero
for grants between other owners; DBA_TAB_PRIVS and the actual consumer checks
confirm the grants exist. That visibility difference was not a grant defect.

The normal registration API registered metadata version 2 with manifest hash
`ec7c532bca41d69a959f4ae998e071216c78236e7ef8361ca9030f9b12c2a9fb`.
The dataset remains unverified and query execution remains disabled. Review
inspected 128 openings, 612 gambits and 4,558 variations; exposed description
and PGN values fit within the 1,000-character bound. Of 740 descriptions, 739
match the pinned comprehensive catalogue; the preserved live Queen's Gambit
record contains D06. Of the PGN values, 4,508 match the comprehensive source
and 50 are preserved earlier lines with chess-token contents. This content
inspection does not establish live model accuracy or semantic correctness.

Live metadata collection as ORAC_PLUGIN sees all 12 view projections but
returns zero keys and zero relationships because base-table constraint
metadata is not visible to that consumer. The release gate remains closed
pending a reviewed architecture decision for exposing only projected
constraint metadata; broad dictionary or base-table grants were not added.

Local implementation adds separated catalogue/general-knowledge prose,
bounded synthesis, compatible result fields and literal APEX/chat presentation.
Those source checks are separate from deployment acceptance. No live model,
chat query, authenticated APEX queue workflow, isolated fresh installation or
rollback acceptance has completed. Browser navigation requires a fresh login
after reimport. Orac was stopped at baseline and remains stopped.

### Query reviewed snapshot and live backend checkpoint — 12-Nov-2026

Subsequent user approval selected a reviewed Core snapshot and authorised the
reviewed pending Core migrations. Those migrations were applied through the
managed runner. The two APEX knowledge query package lifecycle joins were
corrected to use the approved CODE registry projection, which exposes removal
state; their bodies compile. Core query recompile/validity guards now run on
every managed update. No new metadata table, broad dictionary privilege or
base-table grant was added.

The actual installed dictionary review produced 12 view signatures, 23 projected
keys and 33 explicit relationships. The snapshot review ID is
`c40c507e-cea8-4d2e-af5a-73688c3bf946`, with canonical digest
`59b492b1acffba84517d7c897a5f5ed52b56d1afb0e4664c31a025aa0966e279`.
The existing catalogue evidence was populated through the authorised review
operation, verification passed and query execution was enabled. Runtime now
checks bridge-visible signatures against that review and retrieves projected
constraints through the fixed CODE worker API. Enabled runtime manifest loaders
also now apply authoritative registry enablement while preserving the packaged
disabled installation default and manifest hash.

A live backend request using the configured Ollama connector completed in
approximately 60 seconds, returned five real Evans Gambit records and supplied
both catalogue and general-knowledge prose sections with the expected review
provenance. Synthesis took approximately 13 seconds. This is direct backend
acceptance, not authenticated browser or APEX queue acceptance. One generated
general-knowledge sentence incorrectly called the bishop capture forced;
synthesis instructions now explicitly distinguish a gambit offer from optional
acceptance and require “if accepted” where appropriate. A prompt-contract
regression protects that instruction, but does not prove model semantic accuracy.

The managed query worker was verified running. The user-owned private runtime
directory under `var/run/orac` is selected with ORAC_RUN_DIR; use the same value
for start, status and stop so they locate the same runtime state. The standard
/run/orac default remains unchanged. Authenticated APEX queue/browser workflows,
rendered desktop/narrow layouts, isolated fresh-install and rollback acceptance
remain outstanding at this checkpoint.


A subsequent live question, “Which openings are explicitly linked to the Evans
Gambit?”, executed a correct EXISTS/join query and returned Italian Game
(opening ID 196), but synthesis incorrectly denied that any explicit link was
present. The explanation input had omitted SQL/binds and therefore lost the
selection context when only opening columns were projected. The repaired
bounded evidence now includes the validated canonical SQL and scalar binds
inside the same 32 KiB limit. If that context cannot fit, the service returns
the successful table without synthesising context-free prose. Instructions
also preserve nonempty matching associations and avoid unsolicited dates or
biography. This source repair and its deterministic adapter tests require a
fresh live-model check; semantic correctness is not inferred from test success.

### Query release backend and signed-chat acceptance — 12-Nov-2026

The reviewed full Core deployment reported 53 changeset executions including
recurring guards. The APEX knowledge lifecycle join repairs compile, and the
reviewed snapshot remains loaded and verified with query execution enabled.
The managed query worker is active. Production plugin routing now uses its
explicit dedicated semantic Ollama embedding profile instead of constructing
a non-semantic hash test fixture. Cache identity includes routing scope,
provider, endpoint fingerprint, real model, dimensions and profile version.

Signed chat with existing explicit Chess addressing selected the Chess query
capability at score 0.7656 and returned the catalogue-backed Italian Game
relationship, supporting table and SQL. The measured unaddressed relationship
question scored 0.6558 and followed clarification; “What is the Evans Gambit?”
scored 0.5830 and followed ordinary-chat fallback. Existing confidence thresholds,
explicit-address policy and arbitration were preserved; no matching shortcut
or threshold reduction was added.

Direct backend checks rejected the unrelated France question as unsupported
and returned an accurate no-match catalogue result for an absent gambit. A
later explanatory Evans query returned 47 real rows with `complete_clipped`
prose correctly describing b4, the Italian Game and C51 from supplied evidence.
The model returned no separate general-knowledge text. Both renderers now
retain the General chess knowledge heading for successful synthesis and show
“No supplementary general chess knowledge was used.” when that field is empty;
this is a host-authored indication of the empty supplementary field, not a
new model-generated claim. Clarification, unsupported and failed synthesis
responses do not show that successful-answer note.

These are backend and signed-chat checks, not authenticated APEX submission,
queue completion/readback or rendered page acceptance. Browser access still
requires a fresh login. Desktop/narrow visual checks and isolated fresh-install
and rollback acceptance remain unverified. Model samples demonstrated factual
errors earlier in this release, so successful operational checks and revised
prompts do not establish a general semantic-correctness guarantee.

### Final renderer import checkpoint — 12-Nov-2026

The dedicated production routing profile uses local Ollama Nomic embeddings
with 768 dimensions. Measured canonical scores were 0.6558 for the ordinary
relationship question, 0.5830 for the exact unaddressed Evans explanation,
0.4381 for unrelated France and 0.7656 for the explicitly addressed Chess
relationship question. Signed TCP chat selected `orac_chess.query` through
existing explicit-plausible arbitration for the addressed question and returned
the truthful Italian Game association, evidence table and SQL. The handled
reply did not invoke an additional conversational synthesis pass. Its transport
usage counters were zero; that does not mean the underlying query generator
and explanation provider made no model calls.

After the full Core deployment and package repairs, both query APIs are VALID
and installed APEX source validation passes 92 sources. The only remaining
invalid object recorded by the final Core check is the pre-existing KN_SCOPE_BD
baseline object. France was unsupported with empty answer sections. The absent
gambit returned zero rows and a correct catalogue no-match explanation; its
previous supplementary formatting-limit text prompted the instruction repair.
The final Evans backend sample returned 47 rows, `complete_clipped`, correct
b4/Italian Game/C51 prose and an empty supplementary field, now represented by
the fixed successful-answer placeholder in both renderers.

The final managed renderer import correctly refused while Orac held the live
runtime lock. The runtime was stopped through its supported lifecycle before
the managed import succeeded. The manifest fingerprint is unchanged; restart
and post-import gate/worker checks are distinct from the import result. Use
the same private ORAC_RUN_DIR value for start, status and stop. Sign in again
after this final application import to inspect the rendered page.

Local release regression coverage passes 318 tests and 28 subtests; recovery
export consistency and scoped whitespace checks pass. Authenticated APEX queue
submission/completion/readback and desktop/narrow visual acceptance remain
unverified because browser access still requires login. Isolated fresh-install
and rollback acceptance were not run. These remaining gaps prevent a claim of
complete end-to-end acceptance.


Post-import confirmation: Orac restarted successfully from the private runtime
directory. The managed relational-query service reports running, an active lease,
a current tick and no last error. Consumer inspection after import still loads
12 views, 23 keys and 33 relationships for the unchanged reviewed manifest.
The coordinator's final focused subset passed 282 tests and 28 subtests; the
implementer's broader eleven-module suite passed 318 tests and 28 subtests.
The CLI `check` command correctly refuses while the governed runtime holds its
execution lock; the final managed import itself passed readiness before restart.
Browser authentication remains the handoff needed for queue and layout checks.

The balanced workflow reused the approved planner specification
(gpt-6.1-sol, medium) and implementation assignment (gpt-6.1-sol, low).
Independent review was disabled and a separate tester was not configured;
implementation and coordinator verification above are not independent review.

## Strategy release verification — 13-Nov-2026

Development `FREEPDB1` was verified through mapped `orac` inspection and
`orac-db` provisioning connections. The managed bundled Chess installer
completed the strategy deployment and a second install successfully, both
passing readiness. All 740 installed strategy text SHA-256 hashes match the
immutable overlay after the second install. The originally running Orac runner
was restored through its existing `var/run/orac` runtime directory; the TCP bridge
on `127.0.0.1:8765` is ready. No production deployment occurred.

- 128/128 opening/system and 612/612 gambit rows contain strategy. Installed
  word bounds are 88–130 and 84–130 respectively.
- Existing owner identities, names, types, parents and descriptions, and
  variation identities, ownership, parents and move text have identical
  before/after checksums; maximum existing description length was 267 and
  maximum PGN length 204, within the complete checksum input bound.
- All Chess objects are valid with no compilation errors. Application 10030
  remains `ORAC_CHESS_ADMIN`, parsing schema `ORAC_APX_PUB`. APEX metadata
  confirms Description/Strategy sequences 12/13 on P11 (Parent follows at 14),
  and 11/12 on P21. Coordinator browser verification confirmed authenticated
  desktop P11/P21 Description → Strategy → blank spacing → existing data.
  P21 at 390×844 with navigation collapsed wraps readably and scrolls; reload
  retains strategy. Browser checks did not edit/save records; writers were
  exercised through the installed API. Narrow P11 was not separately inspected.
- Opening/gambit query text projections contain all strategy evidence. The
  rollback-only API suite also proves a 4,000-character fixture is projected
  as 2,000 characters with `strategy_truncated=Y`. Dataset metadata is version 3.
- `tests/test_orac_chess*.py`: 158 passed, including deterministic historical
  output, immutable release preservation, exact-position equivalence, all
  740 legal reference replays, pawn-break origins/paths/targets and blocked
  bishop-ray assertions.
- `db/acceptance/verify_strategy.sql` passes adopted first initialisation,
  legacy opening/gambit and ECO writer preservation, explicit null clears,
  source null, absent fields, local edits, upstream updates, reruns, stale
  versions, tombstones and failed-batch atomicity. Fixtures are rolled back.
- The final pre-deployment plan proposed 740 updates, no creations, no
  relationship/parent/owner edge changes and no validation failures. Thirteen
  existing records retained 71 user override details (mostly ECO relationships
  and one description); strategy did not overwrite these changes.

Only the maintained `ORAC_CHESS` schema was available; no isolated fresh-install
target was provisioned or destroyed. Fresh-install execution remains outstanding.
The install order explicitly keeps the legacy opening view through the immutable
historical description seed, then installs the strategy projection and catalogue
API before catalogue releases. The historical description acceptance script is
a check of that legacy lifecycle stage, before the strategy projection.

Strategy prose is original feature-assisted Codex content with targeted editorial
refinements and explicit source/PGN/FEN provenance, not 740 independent human or
engine reviews. Identical reference-position equivalence is recorded in the
overlay rather than inventing differences between equivalent names.


## Query gate renewal and authenticated APEX proof — 13-Nov-2026

The Strategy release changed the installed dataset to metadata version 3 and
manifest fingerprint `3af7a84a79a73a71abffa48479c73c110da3f1af590f6c900244bffe5f3a7fc8`.
The catalogue correctly reset `verified_yn` to N, while retaining the older
version-2 evidence for history. Query submission therefore had no eligible
verified dataset. Source implementation and an earlier successful version-2
backend check did not establish readiness after this release.

The authorised operator reviewed all 740 live strategy values (128 openings
and 612 gambits): every value matches the immutable strategy overlay, and the
maximum length is 869 characters, within the 2,000-character projection bound.
The strategy evidence SHA-256 is
`8b9413b532c0abeb9e7282d36a55e8cf2403156ca004604c5b93dde63fe3e3e3`.
The renewed snapshot was generated from actual installed column/dependency and
enabled, validated PK/UK/FK metadata. It contains 12 views, 23 keys and 33
relationships, review ID `1a90ad21-ec6b-4595-9ceb-c037c1e7457e`, canonical digest
`a8a2bd8f7a88031bb28b0c0bada7dfffa7eb323904b21b104c73973b8c491453`.
The exact version-3 identity was verified through the existing Core API view;
consumer inspection loads the complete reviewed metadata. No gate bypass,
broader grants, source rollback or Strategy release reversal was used.

Authenticated ORAC_ADMIN browser acceptance on application 10030 page 120 now
passes: submitting “What is Evans Gambit?” shows queued status and disables the
button; the managed worker processes request 21; Core records COMPLETED with
`answer_status=complete_clipped` and the new review ID. The same browser session
retrieves and renders 47 rows, a catalogue explanation of the b4 pawn offer,
both labelled prose sections, the explicit no-supplementary-knowledge note and
the evidence-limitation notice. The Ask Chess button becomes available again.
This proves the APEX submission, worker and result-delivery path for the tested
request, rather than only an internal backend call. Desktop screenshot evidence
was captured separately. Narrow layout, cross-session browser denial and
isolated fresh-install/rollback acceptance remain separate outstanding checks.

Every future query projection or manifest version change must renew the live
review for that exact identity before query availability is reported as ready.
A successful managed plugin install alone does not establish that review.


### Overview query and supporting-record presentation source — 13-Nov-2026

The supplied overview result contained 47 joined variation records and 16
columns, repeating entity prose and strategy. Query-generation instructions now
request entity text evidence directly for definitions, reserving related
opening/ECO/move joins for questions that ask for them. Ambiguous entities and
explicit list/variation requests retain their records; no deduplication or
arbitrary first-record workaround was added.

Page 120 keeps the full unchanged returned table inside Supporting records (N)
while displaying the two prose sections first. The native disclosure starts
closed for actual prose and opens for unavailable synthesis or absent actual
answer text. A supplementary placeholder alone is not actual prose. SQL remains
in its own closed disclosure. Readable-width wrapping cells scroll horizontally
inside a labelled keyboard-focusable region. Both exports carry the update;
the recovery export was regenerated.
Metadata version 3, reviewed projections, manifest fingerprint and review state
were not changed by this source update. Local focused query/APEX/admin/strategy
checks passed 136 tests. The final full regression run passed 325 tests and
28 subtests; recovery consistency, compilation and scoped whitespace checks
also passed. Deployment and fresh live/model/rendered evidence must be recorded
separately.

### Compact query live deployment — 13-Nov-2026

The configured live model answered “What is the Evans Gambit?” with one row
and five columns (NAME, DESCRIPTION, DESCRIPTION_TRUNCATED, STRATEGY,
STRATEGY_TRUNCATED), using a name filter on the single text view without joins;
synthesis completed without clipping. The explicit variation-list question
returned all 47 requested rows and two columns (NAME, LINE_KIND) through the
requested gambit-to-variation join, without deduplication. The managed import
initially refused the active governed runner; after stopping Orac through its
private-runtime lifecycle, installation and readiness passed and Orac restarted.
Post-import consumer checks retain metadata version 3, the same 3af-prefixed
manifest hash, verified review and 12 views/23 keys/33 relationships. No schema
or data deletion was performed. Source validation passed 325 tests and 28
subtests, with recovery and scoped whitespace checks passing. Browser reload
requires a fresh login and was left for handoff; the compact rendered layout
has not yet been visually verified.

### Opening Gambit descriptors and details drawer — 13-Nov-2026

The maintained application export and regenerated recovery export now show
Opening Gambit names and description previews instead of identifiers. The
name's declarative APEX link clears page 22 and supplies its protected hidden
`P22_GAMBIT_ID`; page 22 uses the same business authorisation scheme and page
protection as the existing maintenance pages. Its read-only Gambit Details
right drawer reads only `chess_gambit_v`, escapes the name and every chunk of
the full description and strategy, preserves line breaks, and handles an absent
record. Close cancels the dialog without submitting the parent. Page 21 Gambit
maintenance, the opening's link API and row-version handling are unchanged.

Repository dependency searches cover the maintained/recovery exports, tests,
generators and plugin documentation. `GAMBIT_ID` remains an internal join,
primary-key, link-target and association API value. `P11_LINK_GAMBIT_ID` remains
compatible with its existing LOV and processes, while its visible label is
**Gambit** with Link/Unlink help. Other pages' Gambit Id and Link Gambit Id
labels belong to separate maintenance workflows and are outside this change.
No schema, grants, API or application identity change is required.

Validation performed:

- `.venv/bin/python plugins/orac_chess/tools/generate_mle_recovery.py`
- `.venv/bin/python plugins/orac_chess/tools/generate_eco_apex.py --check`
- `.venv/bin/python plugins/orac_chess/tools/generate_mle_recovery.py --check`
- `.venv/bin/python -m pytest tests/test_orac_chess_opening_selector.py tests/test_orac_chess_administration.py tests/test_orac_chess_apex_callbacks.py -q`
  — 36 passed.

These checks validate packaged definitions, escaping and authorisation contracts;
rendered behaviour remains unverified. Before UI acceptance,
verify normal and narrow widths, long/multiline and missing text, absent records,
checksum rejection for tampered IDs, and name links opening the right drawer.
Verify Close preserves an unsaved Opening form and the selected Opening Gambit
view, and that Link/Unlink retain existing locking behaviour. Existing saved
reports should not offer the hidden identifier as a visible column.

The user-authorised DEV import completed through the receipt-aware host importer
into `FREEPDB1`, workspace `ORAC`, application `10030`, parsing schema
`ORAC_APX_PUB`. The live export was backed up under
`/tmp/chess-gambit-import-20261113`; only the Gambit report, its selector and new
page 22 were patched into that backup. Post-import export comparison, normalising
APEX ID offsets, confirmed all 22 unrelated page definitions were preserved.
Unrelated pending repository changes were excluded. The standard display-name
prologue preserved **Orac Chess Administration** under the host alias override.

Installed metadata confirms a numeric `GAMBIT_ID` with hidden display type
`HIDDEN_ESCAPE_SC`, visible escaped Name/Description columns, the name link,
page 22's modal/right-drawer option, protected hidden item and zero drawer
processes. Host SQLcl verified the installation receipt matches the application;
the installed report SQL parses and the drawer renderer compiles without
executing it. Orac was stopped for the maintenance lock and restarted with its
TCP bridge ready. Browser verification reached login after the import reset the
session; authenticated visual/workflow checks above remain outstanding.

The first staging attempt encountered `SP2-0310` because the Oracle container
could not read the copied export; staging permissions were corrected. Import
validation then exposed missing required report-label metadata and an invalid
`HIDDEN` column data type. Failed imports rolled back; the source, recovery and
regression assertions were corrected to retain a label and use numeric type
with `HIDDEN_ESCAPE_SC`, then the final import completed without SQL errors.

### Query Chess status-read recovery — 13-Nov-2026

Page 120 now retries transient status-read failures at most twice per query,
after two then four seconds, using the existing request ID. Successful polls
do not reset that budget, retries count towards the 100-read limit, and the
Ask Chess action stays disabled throughout. Submission is not automatically
retried. Authentication, access, APEX response, parse, cancellation and other
non-transient failures stop immediately with safe reload/sign-in guidance;
raw response bodies and operational errors are not displayed.

Validation passed 32 focused tests with
`.venv/bin/python -m pytest -q tests/test_orac_chess_apex_callbacks.py tests/test_orac_chess_administration.py`.
These include both exports, retry eligibility and exclusions, the total retry
budget, same-ID reads, busy-state restoration, stale timers and the read limit.
The recovery generator `--check` and scoped `git diff --check` also passed.

The receipt-aware managed DEV import applied only page 120 from a live backup.
Post-import export comparison, normalising APEX ID offsets, confirmed that only
page `00120` changed and all other page definitions and the page inventory were
preserved, including the new Gambit Details drawer. Dataset metadata remained
version `3` with verification flag `Y`.

Authenticated browser acceptance remains pending a fresh login. The local
callback tests and installed export comparison do not establish a rendered
browser or live retry-workflow pass.


### Shared-gambit reliability checks — 13-Nov-2026

Transient correction feedback now includes the rejected SQL/binds and a safe
validator explanation, with one correction maximum. Generation explicitly
forbids semicolons and other excluded constructs and requires exact declared
views. The known nested-query false denial was repaired by nearest-local-scope
column resolution; alias shadowing, local ambiguity and non-correlatable
boundaries remain fail-closed. Ordinary column qualification preserves the
existing ORDER BY output-alias and exact reviewed CONNECT BY exceptions.
No grants, schema objects, dataset gate or SQL grammar were broadened.

An initial five-run configured-runtime batch completed five queries and
returned the three correct distinct opening pairs for Queen's Gambit. After
additional qualification/shared-relationship guidance, an intermediate batch
completed one of two runs; the other was denied SQL_SYNTAX after its correction,
without the raw candidate having been captured then. A later instrumented
actual-runtime sample and three generation-only samples did not reproduce that
forbidden-token failure. No speculative normalization was introduced.

After the lexical-scope repair, the final fully captured actual-runtime batch
completed five of five requests on their first generation attempts in
15.84–16.04 seconds. Every request returned three openings: Queen's Gambit,
Queen's Gambit Accepted and Queen's Gambit Declined. SQL used the reviewed
opening-gambit junction with an EXISTS condition requiring the same gambit and
a different opening ID; no singleton relationships were included. Raw diagnostic
candidates were retained only in private /tmp evidence, not production audit.
The final shared-query batch preceded only the hierarchy-specific prompt
compatibility exception; that exception does not affect this question.
Authenticated browser verification still requires a fresh valid APEX session;
no authentication or session checks were weakened to accommodate an expired one.

### Authenticated query verification — 13-Nov-2026

Two consecutive browser submissions of the page's shared-gambit example
completed successfully (requests 47 and 48), displaying prose above initially
collapsed supporting records and SQL. The evidence and SQL disclosures opened
correctly; the first query returned the three distinct Queen's Gambit opening
pairs. A third submission was rejected before queue insertion. Its database
session still had future idle/lifetime limits, while reload required login.
The access log recorded a separate app-1042 login immediately before that
rejection, and the user confirmed using another Orac app during the test.
Apps 10030, 1042 and 1043 share the workspace authentication cookie. This
supports a superseded browser-cookie/session explanation; it is not evidence
of SQL generation failure or ordinary timeout expiry. An isolated fresh-login
browser run was needed to distinguish that interruption. No authentication
controls were changed.

The subsequent isolated authenticated run completed three consecutive instances
of the shared-gambit example (requests 52–54), followed by “What is the Evans
Gambit?” (request 55), without a status or submission failure. The example
answers named the same three Queen's Gambit openings. Evans returned one
supporting row and separate catalogue-grounded and general-knowledge prose,
including the correct b4 offer and an explicitly conditional acceptance.
The disclosures start collapsed and open correctly. Desktop and 390-by-844
layouts were visually inspected; the temporary viewport override was reset,
debugging was disabled, and the authenticated Evans answer was left visible.
The reviewed dataset remained metadata version 3 with verification flag Y.
These passes do not establish elimination of the earlier uncaptured stochastic
SQL_SYNTAX denial or prove the exact cookie value changed during the interrupted
run. They do establish successful live prose and supporting results in a stable
authenticated session.

### Query-page navigation warning — 13-Nov-2026

Page 120 now explicitly sets Warn on Unsaved Changes to No. Its question field
is transient query input, not a maintenance form requiring Save. The canonical
and generated recovery exports carry the native page property; no application-
wide warning handler or maintenance-form behaviour was changed. The 32 focused
APEX checks and recovery consistency check passed. A receipt-aware DEV import
changed only this property in a fresh live application backup. The post-import
export comparison confirmed every other page and all other page-120 definitions
were unchanged. After a fresh login, changing the question to “What is the
Halloween Gambit?” and clicking Openings navigated directly to page 10 with no
JavaScript navigation dialog present. No question submission or catalogue data
edit was needed for this check.

### Prose flow without duplicate record counts — 13-Nov-2026

Successful non-empty query results no longer display a separate row-count
message above the prose. Supporting records (N) retains the count; zero-match
and truncation notices remain. Both exports were updated, with 32 focused checks
and recovery consistency passing. A managed DEV import changed only that status
expression, confirmed against a fresh post-import export. An authenticated Evans
Gambit query displayed the catalogue prose directly, Supporting records (1),
and SQL disclosure without “1 row returned”. Other page definitions, including
the query-page navigation-warning setting, were preserved.

### Query progress encoding and disclosure affordance — 13-Nov-2026

All four query progress messages now use ASCII dots rather than a Unicode
ellipsis, avoiding the three replacement characters found in the installed
export. Supporting records and SQL remain native details/summary disclosures,
styled with the live theme's link colour, underlining, pointer cursor, native
open/closed markers, hover emphasis and a visible keyboard-focus outline.
The canonical/recovery exports and existing retry-message assertion were updated;
32 focused checks and recovery consistency passed. The managed DEV import was
verified against a fresh export: only page 120's CSS and progress punctuation
changed, with all unrelated definitions preserved. Authenticated visual checks
remain pending sign-in.

### Editorial seed deployment — 13-Nov-2026

The user-authorised DEV deployment used the managed bundled Chess installer in
`FREEPDB1`. Target identity was checked through mapped `orac` inspection and
`orac-db` provisioning connections. Administrative SQLcl access was needed for
private Chess data and Liquibase history, which the runtime connection cannot
read. Host SQLcl required execution outside the network-restricted sandbox.

The read-only preflight proposed 740 updates, no creations or relationship/edge
changes, and no validation failures. Existing overrides on 13 records were
preserved. The active Orac runner was stopped to release its maintenance lock;
the managed install succeeded and passed readiness. The runner was restored
using its existing `var/run/orac` directory, with the TCP bridge ready on
`127.0.0.1:8765`.

Post-deployment snapshots verified all 128 opening/system and 612 gambit
strategies exactly match `2026_11_13_editorial_catalogue`, including blank-line
paragraphs. All other owner fields and all 4,558 variations were unchanged.
All 462 prior Liquibase checksums were preserved; the new editorial changeset
was recorded as `EXECUTED`. The existing run-always opening projection and
strategy recompile entries became `RERAN` without checksum changes. No Chess
objects were invalid.

The installed-API `verify_strategy.sql` acceptance suite passed and its fixtures
were rolled back, including multiline source updates, reruns and local override
preservation. A subsequent read-only catalogue plan reported zero creations,
updates, validation failures and ledger changes. Private before/after snapshots
and the installer log are under `/tmp/chess-editorial-deploy-20261113/`.
This verifies the existing DEV upgrade; isolated fresh installation and new
authenticated browser checks were not performed. Query-table whitespace
rendering remains unchanged.
