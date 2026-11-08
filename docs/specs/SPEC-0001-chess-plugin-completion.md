# SPEC-0001: Complete Chess administration and PGN editing

- State: `in-progress`
- Date: 06-Nov-2026
- Owner: Clive Bostock
- Stakeholder reviewer: Clive Bostock
- Technical reviewer: skipped; independent reviewer disabled in the configured profile
- Supersedes: none
- Superseded by: none
- Authority: full MLE integration recommendation accepted on 06-Nov-2026 after
  the successful bounded proof. Privileged deployment remains a concrete final
  approval step; no application-ID migration is authorised.

## Problem and evidence

Chess 0.2.0 has a deployed administration foundation, but games and variations
remain read-only. Completion requires an authoritative Oracle-side PGN validator,
working editing workflows and the remaining runtime acceptance evidence.

Repository evidence:

- [Verification record](../../plugins/orac_chess/docs/verification.md): recorded
  03-Nov-2026; application 100, successful managed upgrades, API acceptance and
  concurrency checks; failed Oracle Java source feasibility gate; remaining
  authenticated browser, fresh-install and utPLSQL work.
- [Administration contract](../../plugins/orac_chess/docs/administration.md):
  PGN semantics, security, versions, locking, images and deployment constraints.
- [Game API](../../plugins/orac_chess/db/schema/package_body/chess_game_api.sql)
  and [variation API](../../plugins/orac_chess/db/schema/package_body/chess_variation_api.sql):
  production source now delegates to the private TAPI with authoritative MLE
  validation; deployed writer state remains pending approved upgrade.
- [Pinned dependencies](../../plugins/orac_chess/vendor/README.md): chesslib
  1.3.6 and Commons Lang 3.12.0, original source pins and checksums.
- Tests: `tests/test_orac_chess_validator.py`,
  `tests/test_orac_chess_administration.py`, `tests/test_orac_chess_schema.py`;
  SQL acceptance assets under `plugins/orac_chess/db/acceptance/`.

These are historical results and current source observations, not a fresh
database verification. The Chess assets are currently untracked alongside
unrelated workspace changes; preserve all existing work.

## Confirmed scope and decisions

1. Complete the existing Chess administration release, including game and
   variation maintenance and its outstanding verification.
2. Stakeholder decision, 06-Nov-2026: investigate an Oracle-side validator first;
   bring alternative architectures back for review if that route is blocked.
   Following comparison, the stakeholder authorised a bounded JavaScript MLE
   proof before further Java source-compatibility work. Retain Java as fallback.
3. Preserve public API contracts where practical, plugin-private ownership,
   host-managed installation, authenticated access and caller-owned transactions.
4. Keep PGN writers closed until authoritative database validation is proven.
5. Exclude engines, AI coaching, MCP, video ingestion, transcripts, YouTube APIs
   and a broader study framework. Full image pixel decoding is outside this
   completion scope; retain the documented bounded validation limitation.

## Ordered implementation plan

### 1. Establish the baseline and impact inventory

Re-read applicable instructions and context before implementation. Capture the
current managed installation, receipt, application identity, object validity,
changeset history and data counts through approved read-only access. Re-run the
existing local checks and compare them with the historical verification record.

Search the repository for producers and consumers of PGN, FEN, `-20020`, header
extraction and game/variation APIs. Classify each as requiring change,
intentionally compatible, obsolete, test-only or unrelated. Include generated
Java assets, private validation packages, public APIs, grants, controllers,
APEX processes, exports, tests and documentation. Record the inventory before
editing, then repeat it at closure.

Exit: current baseline and affected-path inventory recorded; discrepancies have
an explanation. No deployment or data changes are implicit in this milestone.

### 2. Resolve the Oracle validator feasibility gate

Use an approved disposable development target. First prove a pinned JavaScript
MLE candidate behind a private PL/SQL boundary: minimal module invocation,
strict legal PGN replay, FEN checks, long CLOB handling, resource limits and
reproducible install/cleanup. Assess restricted `PURE` execution support in the
actual database. Do not assume PGN import validates every recursive variation.
If MLE fails its gate, review the evidence before selecting the Java fallback.
Java fallback options include a maintained source-compatible dependency set
or externally compiled compatible classes; binary loading changes the former
source-only deployment approach and requires explicit review.

Treat changed versions, reduced dependency surfaces or source adaptations as
candidates requiring evidence, not predetermined fixes. Record licence,
provenance, reproducibility and maintenance implications for each candidate.
Do not edit vendor pins or checksum expectations merely to make checks pass.

Prove the chosen candidate inside Oracle: source compilation, dependency
resolution, PL/SQL invocation, legal and illegal PGN, strict token consumption,
SAN legality, FEN/SetUp agreement and recursive game variations. Run the existing
29-case corpus and extend it for any newly discovered failure modes. Preserve
original PGN text and enforce the documented size and recursion limits.

Exit: a reviewed Oracle-side approach with reproducible runtime evidence and a
forward migration/cleanup design. If no candidate succeeds, report evidence and
alternatives for stakeholder review; do not begin writer enablement or silently
substitute an external service, JAR loader or permissive Java privileges.

### 3. Implement controlled game and variation maintenance

Integrate the proven validator through the private validation boundary. Keep
public signatures stable unless a specific incompatibility is reviewed.
Implement game save/delete and validated header extraction; implement variation
save/delete, parent/owner rules and affected subtree revalidation.

Acceptance includes:

- Games accept legal PGN including recursive RAV and reject invalid moves,
  trailing junk and inconsistent FEN/SetUp headers.
- Variations accept a complete single mainline with comments/NAG and reject RAV.
- Children share the root position and prefix through `branch_ply`; both lines
  have a next move and those moves differ. Reject identical lines, pure
  extensions, cycles and invalid owner/parent combinations.
- Parent edits that invalidate descendants fail atomically. Validation or
  availability failure leaves data and versions unchanged.
- Stale versions, restrictive deletes and association integrity remain enforced.
  Callers retain commit/rollback ownership.
- Concurrent root creation and competing parent/child edits cannot bypass
  hierarchy or version checks; retain deliberate write serialisation unless a
  separate design change is justified.

Deploy using forward changesets and the managed lifecycle. Preserve the
161-changeset baseline and executed diagnostic history. Never reactivate the
failed diagnostic controller, reset checksums or recreate the existing schema.
Retain fail-closed behaviour when validator objects are missing or invalid.

Exit: database acceptance passes for writes, failures, rollback, permissions,
branches, subtree changes and concurrency.

### 4. Complete APEX workflows

Enable game and variation editing only after milestone 3. Implement and verify
paste/header assistance: explicitly invoked extraction fills empty metadata
fields while preserving populated user values; ordinary saves preserve the
separate searchable metadata contract. Confirm this proposed interaction with
the stakeholder before implementing it.

Verify create, edit, delete, cancel, validation messages, stale-version handling,
parent/subject LOVs and navigation. Exercise existing reference maintenance,
image replacement/delivery and association workflows as regression coverage.
Test authorised access, insufficient roles, unauthenticated access and plugin
disablement, including image delivery.

Export the verified app through SQLcl into the canonical asset, preserving the
stable alias, parsing schema, host return navigation and receipt sanitisation.
Resolve application identity against the current root context before this
milestone. It records existing app 100 and stakeholder-reserved replacement
10030, with migration pending. Coordinate that separately approved migration
with managed receipts; do not import to an inferred or unrelated application.
The bounded MLE proof makes no APEX changes.

Exit: authenticated browser evidence covers each workflow, including failure
paths. Source parsing and login rendering alone do not satisfy this milestone.

### 5. Close installation and test infrastructure gaps

Confirm the approved isolated schema/container and provisioning route for a
fresh installation. Confirm separate `UTPLSQL_DEV` topology and provisioning
authority before installing the framework; do not bundle it with the plugin.
Author repository-integrated deterministic suites for public behaviour and
permission boundaries, retaining separate concurrency and browser checks.

Run a fresh install with semantic acceptance, upgrade from the deployed fallback
with representative data, and repeat managed installation/export roundtrips.
Verify object validity, grants, constraints, receipts, app identity and data
preservation. Fresh and upgrade paths must agree on functional readiness.
Fixture cleanup must be scoped and verified; no account or credential belongs
in source or test evidence.

Exit: fresh installation, upgrade, repeatability and utPLSQL runs pass, with
commands, target identity and actual results recorded. Missing prerequisites
remain explicit blockers rather than waived checks.

### 6. Review and release handoff

Repeat dependency searches and explain every remaining disabled-path reference.
Update README, administration documentation, verification record, manifest and
version metadata as required by the final change. Record the chosen validator,
provenance, migrations, operational limits and recovery procedure.

Obtain independent review of requirements, security, migration and acceptance
evidence under the configured implementation workflow. Agree a release commit
scope that includes the currently untracked Chess assets and excludes unrelated
work. Mark this specification `done` only when every acceptance criterion has
evidence and no completion blocker remains.

## Migration and recovery constraints

- Existing public APIs, views and APEX consumers form the compatibility surface.
  Record any intentional contract change and all affected consumers.
- Existing DEV has recorded failed-spike history; fresh targets do not. Design
  migrations for both histories without deleting history or resetting checksums.
- Retain existing data, host application receipts and least-privilege grants.
- Document a recovery path that restores fail-closed PGN writes and read-only
  forms without deleting games or variations. Test it on the disposable target.
- Production, privileged provisioning and destructive operations require their
  applicable explicit authorisation. This specification does not itself approve those runtime actions.

## Dependencies, risks and open questions

- Remaining evidence gaps: isolated fresh installation, authenticated browser
  workflows/layout and utPLSQL integration. Approved DEV managed deployment,
  production/consumer acceptance, concurrency and recovery/reapplication passed.
- Need an existing authorised APEX test session/account, an approved fresh target
  and a confirmed utPLSQL development topology.
- Accepted integration uses an explicit fill-empty-fields action; existing metadata
  is never overwritten by header extraction.
- The bounded MLE feasibility gate passed on DEV on 06-Nov-2026. Production
  source integration and the approved DEV runtime checks have passed.
- Bounded proof assignments resolved from the `balanced` profile on 06-Nov-2026:
  planner and implementer `gpt-6.1-sol`, reasoning `low`; reviewer disabled;
  tester not configured. Separate planning and implementation workers were
  invoked with those settings. Full integration assignments were re-resolved by the coordinator.

## Verification evidence

Created from the linked repository evidence on 06-Nov-2026. Subsequent bounded
read-only DEV inspection verified ORAC/FREEPDB1, version 23.26.0.0.0, and
`DBMS_MLE.get_available_languages()` returned `JAVASCRIPT`. That does not prove
module execution or the validator. No database modifications were made during
that inspection. Following explicit privileged-action approval, the stored MLE
proof passed all 44 runtime cases on DEV, including size/depth limits and CLOB
input/output above 64K. Removal/reinstall/retest passed, final proof object count
was zero and no invalid Chess objects remained. See the
[runtime evidence](../../plugins/orac_chess/docs/mle-feasibility.md).
The stakeholder subsequently accepted the recommendation to integrate MLE.
Approved DEV managed deployment passed, preserving installed 100 and receipt 100.
Production corpus 45, consumer API 60, session-only unavailable-runtime failure,
APEX source 75, both concurrency scenarios, cleanup, read-only recovery, withdrawal
and managed reapplication passed on 07-Nov-2026. Fresh install, authenticated
browser workflows and utPLSQL remain pending; this specification stays in-progress.


## Integration impact and current handoff

The changed contract is authoritative PGN maintenance behind unchanged public
PL/SQL signatures. Production controllers, private validation/TAPI, public game
and variation bodies, editable APEX31/61, generated runtime/recovery/corpus,
host owner privilege reconciliation and their focused tests require changes.
Base tables, grants, alias, installed application 100, receipt/roles and original
161-changeset history remain compatible. Java diagnostics and their historical
failure record intentionally remain outside deployment. Portable proof sources
are test-only evidence; they do not substitute for production acceptance.

The owner needs CREATE MLE only for the fixed Chess plugin/schema pair. Final
runtime scope must preserve application 100 and the existing host receipt, run
managed upgrade/repeat and rollback fixtures under the approved consumer, verify
object validity, then review withdrawal/reapplication and a fresh approved target.
Authenticated UI layout/workflow and absent utPLSQL remain explicit verification
gaps. No LOGGER, engine, MCP, AI or ingestion work is included.


### Runtime continuation, 07-Nov-2026

User approval covered the concrete DEV deployment and acceptance bundle. History
advanced 332 to 340 without baseline resets; all 7 private MLE objects were VALID.
Application100 and its receipt were preserved. Parent/child and competing-root
sessions observed 34.09s and 33.45s lock waits, and reserved fixture cleanup left 0.
Withdrawal removed 7 MLE objects with invalid 0/history 340 retained; read-only export
had 0 edit buttons and writers refused PGN mutations. Ordinary managed reapplication
passed. See the [verification record](../../plugins/orac_chess/docs/verification.md)
for evidence and remaining checks. The canonical export now comes from actual
app 100 using original IDs, retains default 10030 and sanitises receipt UNATTESTED.
Independent review remains disabled by configuration; no independent tester or
review outcome is implied. Fresh target, expired browser session and absent
utPLSQL remain release gaps.


Authenticated browser inspection on 07-Nov-2026 exposed three existing UI source
issues: escaped/stale welcome content, date conversion in the game-load INTO
target, and missing PL/SQL language declarations for dynamic hierarchies. All
were corrected and the managed import passed. The strengthened source checker
passed 75 sources using a non-entered PL/SQL wrapper to force bind compilation.
The actual corrected application 100 was exported back to canonical source and
recovery regenerated; 20 focused Chess tests and generator checks passed. Full
browser workflow/layout acceptance remains pending after reimport reset the
session. These corrections do not close fresh-install or utPLSQL gaps.
