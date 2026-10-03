# Orac plugin removal — continuation brief

Prepared 13-Sep-2026; acceptance updated 19-Sep-2026. This is an IMPLEMENTATION continuation, not a planning task.

## Mandatory environment and authority

Work directly in the SAME Local checkout /home/clive/PycharmProjects/Orac on develop. The originating task verified this branch and the dirty working tree immediately before hand-off. Do not create a worktree, clean checkout, new branch, or fresh clone. Do not reset, revert, stash, discard, overwrite, or restart the existing implementation. Preserve all tracked and untracked changes, including unrelated work that predated this feature.

Authority order:
1. The user's approved clean-build implementation plan below defines intended behaviour.
2. The current Local working tree defines actual implementation state.
3. This continuation brief explains progress, risks and remaining work; verify it against the code.

First read applicable AGENTS.md, AGENT_CONTEXT.md, skills and guardrails and inspect git status/diffs. Then complete ONLY unfinished work. Do not redesign, broaden scope, introduce new architecture, or refactor unrelated code. No actual destructive database operations to prove the feature. Use existing mocks, safe acceptance/rollback mechanisms and established test infrastructure. No development-database rebuild or migration is authorised. No commit was requested.

## Approved implementation plan and architectural constraints

This is the execution contract from the user's approved “Orac plugin removal: clean-build implementation plan,” preserving its decisions rather than reverting to earlier proposals.

### A. Current operational registry and small lifecycle

Keep one plugin_registry row per unique logical plugin_id and the existing ordinary surrogate plugin_registry_id. Python management continues to identify plugins by plugin_id. enabled remains the sole enablement authority:
- Y: installed and potentially runnable, subject to readiness.
- N: installed but non-runnable, with operational state retained.
- No row: uninstalled.

Do not add permanent REMOVED rows, multiple historical rows per plugin, a second plugin identity abstraction, or universal installation-generation identifiers. Reinstall naturally creates a fresh surrogate registry key and fresh knowledge scope. Old history never revives a registration or influences a new installation.

disable preserves configuration, schema and operational resources; enable validates current registration and readiness. Enable cannot recreate an absent plugin or override an incomplete removal. Removal progress belongs in a small durable removal operation, not another enablement/status source of truth. Incomplete removal leaves the current registration disabled and blocks installation, upgrade, check/status writers, service policy and APEX toggles.

### B. Historical knowledge scope ownership

The current design originally tied immutable, undeletable knowledge_scopes to plugin_registry_id; registry deletion was prohibited to protect history. Preserve that integrity without keeping dead operational registrations.

Clean-build end state:
- knowledge_scopes PLUGIN owners use immutable plugin_id attribution, not a FK to the operational registry.
- PROJECT scopes retain existing project_id ownership.
- knowledge_scope_id is the permanent historical domain identity.
- Add irreversible retired_on for plugin scopes.
- Current plugin_registry has a required immutable knowledge_scope_id association to a matching, non-retired PLUGIN scope.
- Fresh registration and fresh scope creation occur together through existing controlled APIs/TAPIs. Existing-row updates retain their association. Never locate/reuse old scopes by plugin name.
- Current name resolution follows the registry's exact scope association.
- Historical reporting uses scope identity and immutable attribution, not a later registry row joined by name.
- Pending removal makes the scope operationally ineligible; final removal retires it and deletes registry in one Core transaction.
- Retain scope no-delete protection and immutable privilege identity. Replace blanket registry no-delete with guarded finalization.

Historical RAG privileges, sources, documents, versions, ingestion/retrieval lineage and accepted shared Core knowledge survive, inert where the plugin scope is retired. Do not delete shared project knowledge merely because its producer plugin is removed.

### C. Scope-bound sources and queued work

knowledge_source_objects uniqueness becomes (knowledge_scope_id, source_type, source_reference). Full-key lookup is mandatory; existing source scope ownership must never be changed. Remove ordinary-ingestion legacy rekey/reparent behaviour from the clean-build path.

ID-based RAG/authorization calls must preserve the supplied ID; never turn it into a plugin name and resolve a successor scope. Retired/ineligible scopes must be excluded from claims, publication and retrieval. Cancel outstanding work targeted at a retiring plugin scope with a specific retirement reason.

Drop Box:
- Resolve and store target scope ID on locations; snapshot onto jobs.
- Names remain input/display conveniences, resolved only when an administrator creates or explicitly changes a target.
- Enqueue and Core handoff validate the pinned ID against the current eligible target.
- Old locations/jobs cannot follow a removed-and-reinstalled plugin's reused name. Explicit reconfiguration is required.
- Extend existing CODE/PLUGIN bridge validation packages; no cross-schema table grants.
- Use the producer's existing plugin scope ID where provenance needs to distinguish reused private job numbers, not a universal installation ID.
- Same-project shared content retains stable domain deduplication and accepted Core ownership.

### D. Two narrow durable stores

Removal operations record operation ID, plugin ID, expected registry key snapshot (not permanent FK), scope ID, version/manifest hash, schema disposition, authorised database/PDB target, bounded credential-free resource inventory, actor/confirmation/timestamps, verified per-resource checkpoints, sanitised errors and completion. At most one incomplete operation per plugin. Completed records support history/idempotent response recovery, not operational inventory.

Schema ownership receipts record database/PDB identity, declared dedicated schema, actual Oracle user identity and creation evidence, plugin/current-registration association, privileged provisioning provenance, OWNED/RETAINED/DROPPED disposition and removal reference.
- Only the privileged provisioning/removal path can attest ownership.
- New registration cannot adopt an existing user.
- Retry/upgrade requires receipt matching current registration and actual schema incarnation.
- Names, manifest declarations alone and deployment-success rows do not prove exclusive ownership.
- Uncertain provisioning ownership fails closed, including crash after CREATE USER before a trustworthy receipt.

### E. CLI contract

Extend existing bin/orac-plugin.sh -> src/controller/orac-plugin.py -> PluginInstaller. No parallel uninstall subsystem.

Commands:
- disable <plugin_id>
- enable <plugin_id>
- remove <plugin_id>
- remove <plugin_id> --keep-schema
- remove <plugin_id> --dry-run --json
- history <plugin_id> --json

Normal remove destroys only verified dedicated plugin-owned schemas as part of a genuine uninstall. This is the approved later design, superseding the older keep-schema-by-default/optional --drop-schema proposal. Destructive execution STILL requires explicit acknowledgement:
- Interactive inventory shows plugin, database/PDB, schemas and other owned resources, and explains --keep-schema. Require a typed phrase identifying plugin and schema destruction.
- Non-interactive requires --yes; if schemas will be destroyed also require --confirm-schema-drop <plugin_id>.
- Acknowledgement identifies the plugin, never an arbitrary username.
- --keep-schema and destructive acknowledgement are mutually exclusive.
- No force bypass of protections/dependency checks.
- Schema-less removal works normally; --keep-schema explains there is no schema.
- Dry run is read-only and stops before journal/fence/cleanup.
- Exit codes 0 success/idempotent completion, 1 operational failure, 2 invalid arguments or missing/declined confirmation.

Normal installed listing excludes removed registrations. Keep source-package inventory explicitly distinguishable. Status reports current registration; history is explicitly historical. Do not expose a usable remove command until mandatory cleanup/recovery are complete and tested.

### F. Schema/resource safety

Use existing manifest validation, host-owned bridge catalogue and Docker/SQLcl administrative deployment architecture. Do not use runtime connection for DROP USER or accept a supplied database username.

Preflight/revalidate:
- Installed manifest identity/hash and registry declarations.
- Receipt + actual user incarnation + exact database/PDB.
- Protect ORAC, ORAC_CORE, ORAC_API, ORAC_CODE, ORAC_PLUGIN, ORAC_APX_PUB, Oracle-maintained/common users and all other host-protected/shared/unrelated schemas.
- Inspect cross-schema FKs, dependencies, sessions, grants, synonyms, Scheduler/jobs, ACLs and external resources as applicable.
- Unknown dependencies or insufficient inspection privilege block removal.
- Only verified owned resources/grants may be removed. Never remove shared schemas, roles, workspace or unrelated objects.
- Already-missing verified schema is idempotent success; same-name recreated user is NOT.
- --keep-schema preserves application objects/data while disconnecting grants, locking the dedicated account where appropriate, removing APEX/services and stopping autonomous resources. Unknown/unmanageable jobs block completion.
- Ordinary reinstall refuses deliberately retained or unexpected pre-existing schemas. Adoption/reset is excluded from v1.

Bundled ownership: home_assistant -> ORAC_HA, services/private state, app 10010; drop_box -> ORAC_DROPBOX, scanner/config/jobs/events, approved Core bridge grants, app 10020. weather/media_control have no declared dedicated schema. Plugin APEX apps share workspace/parsing infrastructure which must survive. Inspected payloads did not identify Scheduler/ACL/synonym resources, but live preflight still must check.

### G. Services/APEX/config/files/audit

Delete PLUGIN-owned plugin_services rows for the exact current registration; preserve synthetic Core services. Delete operational capability/entitlement summaries with the registry; investigate real additional stores instead of inventing them.

Extend PluginApexAppInstaller/DockerPluginApexAppInstaller and existing install-plugin-apex-app.sh administrative architecture with verified removal:
- App ID, alias, workspace and installation receipt must match; persist trustworthy install receipt before ordinary operation.
- Disable actual execution and check independent activity; hiding a menu is insufficient.
- Add plugin-specific lifecycle authorization and update plugin exports home_assistant/apex/f10010.sql and drop_box/apex/f10020.sql.
- Preserve generic Core role helper used by Core apps, shared workspace and parsing schema.
- Remove application first, then delete operational plugin_apex_apps rows; retain diagnostic summary in journal.

Configuration:
- PluginSecretVault.delete_plugin exists; use it for one section, with atomic replacement/locking for shared vault updates.
- Delete registered managed configuration directory.
- New installation uses plugin.ini.example/defaults, not stale developer-source plugin.ini. Preserve deliberately configured files on retry of the same incomplete installation.
- Remove only verified installed snapshots/generated state under host-managed roots with containment and symlink protections.
- Preserve developer plugins/ source, external data directories/documents, shared Python interpreter dependencies, diagnostic logs and inert package archives. No pip uninstall or deletion of external accounts.

Deployment ledger: delete plugin_db_deployments operational rows at final removal so old checksums/successes never skip fresh deploy.
History: preserve plugin_invocations/plugin_audit_events snapshots without adding registry FKs.
Extend existing PluginAuditAdapter for lifecycle events with plugin/version, operation/scope IDs as relevant, actor, confirmation, outcome and sanitised diagnostics; do not fabricate conversation context for CLI.
Capture necessary service/APEX/deployment summaries before deletion.
Restore recovery must respect incomplete removal, never reconstruct registration from completed history.

### H. Maintenance, ordering and retry

Maintenance-only v1, one governed host per database. Supported runtime/foreground entrypoints hold shared stable execution lock; mutations require exclusive lock and refuse while execution is active. Keep Oracle running. Stable lock must live outside PID-cleanup paths. Unsupported remote execution must block safe removal. No online drain/distributed framework.

Sequence:
1. Acquire exclusive maintenance access and serialize management.
2. Read-only preflight current row/manifest/scope/receipts/paths/APEX/dependencies/privileges.
3. Confirm bounded inventory, schema disposition and database target; revalidate.
4. Atomically commit disabled registration + durable removal fence.
5. Quiesce independent APEX/database/autonomous execution; unknown activity fails closed.
6. Checkpoint external cleanup: APEX apps, verified grants/resources, then schema drop or retain/detach. Recheck identities before destructive calls.
7. Checkpoint managed configuration/secrets/files/cache cleanup.
8. One Core transaction: retire scope, cancel targeted pending work, preserve histories, delete operational service/APEX/deploy rows, complete operation, delete registration.

Mandatory cleanup precedes registry deletion. Never return “removed” with mandatory cleanup pending. Retry resumes exact registration/disposition; inspect external actual state after lost replies. A successful drop followed by metadata failure leaves disabled/resumable state. Do not recreate schema or re-enable as rollback. Changed schema incarnation/database/receipt stops recovery. Final Core changes roll back atomically. A lost success reply can return completed history safely; an old operation cannot affect a successor registration.

### I. Clean-build delivery and tests

No migration/preservation of current development database. Canonical DDL only: required columns directly in plugin_services/knowledge_ingestion; remove superseded source/document type/key conversion/backfill chains; correct project seed/setup via canonical APIs. Update associated views, specs/bodies, grants, annotations/comments and controllers coherently. Root SQLcl -> productController -> schemaController -> object includeAll ordering must work with optional plugins absent.

Test disabled/enabled/schema-less removal; keep/drop semantics; protected/shared/forged/inconsistent ownership/wrong PDB/recreated user; missing schema; lifecycle fencing and no direct revive; fresh reinstall/new scope and registry keys; historical preservation and no operational carryover; same reference in distinct scopes; same-project dedup; immutable source ownership; exact-ID RAG; Drop Box stale queue targets; dependency rejection; all checkpoints/failures/retry/lost final response; deployment/APEX collisions; config/vault/path/Core/shared preservation; history vs normal listing; clean-build controller coverage. Use Oracle/APEX integration only via safe authorised infrastructure, never actual destructive operations against user's database. Mocks/static assertions are not proof of DDL execution.

Explicit exclusions: permanent removed rows, universal generations, generic lifecycle frameworks, online/distributed remove, retained-schema adoption/reset, automatic backup/export, arbitrary uninstall hooks, external account/doc deletion, shared dependency removal, bypassing uncertain ownership.

## Implementation state — validated 19-Sep-2026

Implementation and the authorized acceptance checks are complete. The user
approved staging the 47 listed files and explicitly authorized destructive
acceptance only in a disposable environment. That approval supersedes earlier
no-live-testing notes for this isolated target only.

The existing database was never connected to or modified. Acceptance used
`orac-removal-acceptance-20260914`, labelled
`orac.acceptance=plugin-removal-20260914`, with no host mounts, no published ports,
and network mode `none`. Its PDB was created independently from the local image;
no existing database volume or data was copied. The container is stopped after
validation and retained for inspection. No commit was made.

### Delivered behaviour

- Clean-build Core DDL separates immutable historical plugin scopes from the
  current registry. Reinstall creates a fresh registration and scope. Sources
  retain immutable scope/type/reference identities; exact-ID authorization and
  ingestion eligibility reject retired targets.
- Drop Box locations and jobs pin target scope IDs. Jobs also record the producer
  scope ID, so a reused private job number cannot imply the same installation.
  APEX reports join the pinned scope, and explicit location reconfiguration
  affects future jobs only. Project source deduplication remains unchanged.
- Two narrow stores hold removal operations and privileged schema receipts.
  Controlled APIs fence the exact current registration, checkpoint progress and
  atomically retire/cancel/delete operational state and complete the journal.
  Completion and enable/disable events use the existing audit subsystem.
- Privileged provisioning and schema cleanup use the selected Docker Oracle
  administrative boundary. Preflight verifies PDB/user incarnation, receipts,
  grants, sessions and dependencies. DROP and KEEP are immutable dispositions;
  retained users remain locked/detached. A never-provisioned, still absent schema
  is recorded as NOT_PROVISIONED without fabricating ownership.
- APEX imports record a per-application setting marker and a privileged receipt;
  the import session repeats ownership checks. Cleanup verifies that receipt,
  disables the application, checks activity and removes only the owned app,
  preserving shared workspace/parser resources. Bundled plugin authorization
  checks current installation availability without caching the result.
- Installer orchestration implements dry-run inventory, explicit confirmation,
  durable fencing, external cleanup, vault/config/snapshot/cache cleanup,
  checkpoint recovery and lost-final-response recovery. Failed installations
  retain verified package snapshots for removal. Files are traversed using
  descriptors and identity checks; source packages are preserved.
- The CLI exposes disable, enable, remove, history and explicit source inventory.
  Default removal drops verified dedicated schemas; KEEP locks/detaches them.
  Noninteractive destruction requires both target acknowledgements. There is no
  force mode or retained-schema adoption.
- Supported runtime/service/maintenance entrypoints use the same single-host
  execution lock. PAT management also participates. Removal retries clear vault
  credentials again even after a saved files-complete checkpoint, and preserve a
  sanitized recovery error when both cleanup and history access fail.
- Canonical operator guidance is in docs/plugins.md; Drop Box guides explain
  pinned scopes and durable provenance. New columns have comments/annotations.
  Core controllers discover production SQL assets through their existing chains.

### Validation and evidence

- Full unittest discovery after implementation fixes: **1,572 tests run, zero failures,
  two skipped**, 24.503 seconds. Log: /tmp/orac-final-validated-suite2.log.
- Final focused database, CLI-wrapper, Drop Box and removal checks: **116 passed**.
  Log: /tmp/orac-acceptance-final-focused.log.
- Core SQLcl Liquibase clean-build installation completed with **1,414 recorded
  changesets**. After recompilation, all six Orac schemas had zero invalid
  objects and zero compilation errors. APEX 24.2 reports VALID on Oracle Free
  23.26.0.0 (26ai image). Installation was resumed after correcting defects below.
- The rollback-only Core acceptance script passed: enable/disable, durable
  fence, incomplete-finalization rejection, irreversible retirement, fresh
  reinstall registry/scope keys, and old-operation retry preserving a successor.
- Actual production-generated schema helpers passed NOT_PROVISIONED inspection,
  receipt provisioning/retry, wrong-PDB identity rejection, unexpected role
  rejection, DROP/KEEP, cleanup retries, retained-schema adoption refusal,
  unreceipted-user rejection, recreated-user preservation and lost-DROP-reply
  recovery. Five DROP and one KEEP operations completed in the disposable
  journal, with five DROPPED and one RETAINED receipts.
- Bundled Drop Box APEX import, receipt marker tampering rejection, application
  removal and repeated removal passed. Shared ORAC workspace and ORAC_APX_PUB
  parser survived. The changed Core APEX 1042 export imported successfully.
- The actual Drop Box installer validated and deployed its complete plugin
  Liquibase payload; all private objects compiled. A rollback-only enqueue test
  confirmed the exact target and producer scope IDs and rejected queued target
  mutation with ORA-20409. Removing that fully deployed payload preserved Core
  APEX 1042 and historical scopes.
- Logs: /tmp/orac-live-schema.log, /tmp/orac-live-apex.log,
  /tmp/orac-live-recovery.log, /tmp/orac-live-payload.log,
  /tmp/orac-live-final-cleanup.log, /tmp/orac-live-core-apex.log and
  /tmp/orac-acceptance-final-dictionary.log. The isolated execution harness is
  /tmp/orac-removal-live.py; it asserts container label, no mounts and no network
  before dispatching. These temporary artifacts are not production install assets.
- scripts/check_core_liquibase.py, Bash syntax and git diff --check passed.
  Direct Black formatting was applied to changed model code. Earlier targeted
  Ruff passed for six model modules; known pre-existing CLI E402 bootstrap and
  eight mypy findings are not claimed resolved by this feature.

### Fault classification and fixes found by acceptance

Observed facts: the reported voice test omitted `meta.channel`, while both
speech routing and playback subscription require `channel: voice`. Adding that
field made the isolated test and full suite pass with no runtime change.
Derived conclusion: the reported failure was an incomplete test request, not a
plugin-removal voice regression. Remaining hypotheses for that failure: none.

Live database testing found and fixed:

1. A service comment and annotation used `owner_type` instead of the actual
   `service_owner_type` column.
2. Runtime grants on the new history views requested SELECT despite their
   underlying READ grants. Runtime now receives matching READ access.
3. PDB switching resets DBMS_OUTPUT. Administrative schema/APEX helpers now
   enable output after the switch so result markers reach their callers.
4. APEX staging assumed database deployment had already created a writable
   directory. It now creates its own bounded directory with Oracle ownership.
5. SQLcl can return zero after a connection failure. The Core deployment wrapper
   now detects that output and fails instead of reporting validation success;
   a regression test covers this exact observed failure.
6. Drop Box annotations referenced protected Core storage. Their relationship
   basis now names the approved scope-validation bridge.
7. Drop Box seed inserts omitted the required pinned scope ID. They resolve and
   persist it now. Obsolete seed DML that reassigned queued jobs was removed.

### Completion and limits

The authorized implementation and validation work is complete; no user action
is required to finish these checks. The approved 47 new files are staged with
their latest fixes; changes to previously tracked files remain unstaged. Review
and commit were not requested. No migration of the existing database is supplied.

Acceptance covers the tested local Oracle/APEX versions and governed single-host
workflow. It does not claim production deployment, rendered browser UI testing,
distributed coordination, ungoverned admin race elimination, or exhaustive
validation of every possible Oracle installation. The two skipped Python tests
remain skipped; existing unrelated typing/lint findings remain documented.

### Tradeoffs and operating constraints

This is a clean-build change, with no migration or automatic legacy adoption.
Uncertain ownership fails closed. Independent external resources cannot share a
single transaction, so exact receipts and durable checkpoints support recovery.
Retained schemas require separate administrative resolution before reuse. No
external account deletion, arbitrary uninstall hooks, shared dependency removal,
backup/export, distributed lock or new generic lifecycle framework is included.

Guardrails applied: clean-build schema/controller consistency; immutable history
and exact-scope authorization; privileged ownership verification; approved host
maintenance boundaries; canonical Core/plugin documentation; focused failure
and recovery testing; preservation of user-owned changes and explicit staging.

### New files approved for staging

These 47 files form the approved, staged removal feature set. Unrelated Home
Assistant files and the existing image are excluded. No commit was made.

- `docs/pending_work/plugin-removal-continuation.md`
- `plugins/drop_box/db/schema/annotation/drop_job.sql`
- `plugins/drop_box/db/schema/annotation/drop_location.sql`
- `resources/db/acceptance/plugin_removal_lifecycle.sql`
- `resources/db/schema/orac_api/grant/plugin_removals_code_access.sql`
- `resources/db/schema/orac_api/grant/plugin_removals_tapi_code_access.sql`
- `resources/db/schema/orac_api/grant/plugin_schema_ownership_code_access.sql`
- `resources/db/schema/orac_api/package_body/plugin_removals_tapi.sql`
- `resources/db/schema/orac_api/package_body/plugin_schema_ownership_tapi.sql`
- `resources/db/schema/orac_api/package_spec/plugin_removals_tapi.sql`
- `resources/db/schema/orac_api/package_spec/plugin_schema_ownership_tapi.sql`
- `resources/db/schema/orac_api/privilege/plugin_removals_core_access.sql`
- `resources/db/schema/orac_api/privilege/plugin_schema_ownership_core_access.sql`
- `resources/db/schema/orac_api/trigger/plg_remov_bu.sql`
- `resources/db/schema/orac_api/trigger/plg_schown_bu.sql`
- `resources/db/schema/orac_api/trigger/plgreg_bi.sql`
- `resources/db/schema/orac_api/view/plugin_removals_v.sql`
- `resources/db/schema/orac_api/view/plugin_schema_ownership_v.sql`
- `resources/db/schema/orac_code/grant/plugin_removals_runtime_access.sql`
- `resources/db/schema/orac_code/grant/plugin_schema_ownership_runtime_access.sql`
- `resources/db/schema/orac_code/view/plugin_removals_v.sql`
- `resources/db/schema/orac_code/view/plugin_schema_ownership_v.sql`
- `resources/db/schema/orac_core/annotation/knowledge_scopes.sql`
- `resources/db/schema/orac_core/annotation/knowledge_source_objects.sql`
- `resources/db/schema/orac_core/annotation/plugin_apex_apps.sql`
- `resources/db/schema/orac_core/annotation/plugin_registry.sql`
- `resources/db/schema/orac_core/annotation/plugin_removals.sql`
- `resources/db/schema/orac_core/annotation/plugin_schema_ownership.sql`
- `resources/db/schema/orac_core/annotation/plugin_services.sql`
- `resources/db/schema/orac_core/comment/plugin_removals.sql`
- `resources/db/schema/orac_core/comment/plugin_schema_ownership.sql`
- `resources/db/schema/orac_core/constraint_other/plg_remov_ck1.sql`
- `resources/db/schema/orac_core/constraint_other/plg_remov_ck2.sql`
- `resources/db/schema/orac_core/constraint_other/plg_remov_ck3.sql`
- `resources/db/schema/orac_core/constraint_other/plg_schown_ck1.sql`
- `resources/db/schema/orac_core/constraint_other/plg_schown_ck2.sql`
- `resources/db/schema/orac_core/constraint_other/plg_schown_ck3.sql`
- `resources/db/schema/orac_core/constraint_pk/plg_remov_pk.sql`
- `resources/db/schema/orac_core/constraint_pk/plg_schown_pk.sql`
- `resources/db/schema/orac_core/index/plg_remov_fidx1.sql`
- `resources/db/schema/orac_core/index/plg_remov_pk.sql`
- `resources/db/schema/orac_core/index/plg_schown_fidx1.sql`
- `resources/db/schema/orac_core/index/plg_schown_pk.sql`
- `resources/db/schema/orac_core/table/plugin_removals.sql`
- `resources/db/schema/orac_core/table/plugin_schema_ownership.sql`
- `src/model/plugin_execution_lock.py`
- `tests/test_plugin_removal_foundations.py`

## Protect pre-existing unrelated edits

At the beginning of implementation there were already substantial changes in:
- docs/pending_work/TODO.md, docs/plugins.md;
- home_assistant manifest/version/config, client/control/repository/service/sync/plugin and DB/API/view changes, requirements, README/docs;
- pyproject.toml and poetry.lock;
- src/model/plugin_router.py and src/model/plugin_runtime.py;
- tests/test_home_assistant_*, test_plugin_bumpversion.py, test_plugin_database_deployment.py, test_plugin_installer.py, test_plugin_runtime.py;
- untracked home_assistant/capabilities.py, associated tests/fixtures/docs and orac-rag-usage-privileges.png.
These are NOT disposable removal work. Preserve them. The removal work changed src/model/plugin_installer.py; the dirty tests/test_plugin_installer.py already existed at the start. Inspect overlapping diffs carefully. Router/runtime changes are pre-existing, not new removal implementation.

## Useful repository paths/findings

Root architecture: bin/orac-plugin.sh -> src/controller/orac-plugin.py -> src/model/plugin_installer.py.
Provisioning/deploy: src/model/plugin_database_deployment.py; resources/docker/oracle/bin/deploy-plugin-db.sh and deploy-plugin-liquibase-db.sh.
APEX: PluginApexAppInstaller/DockerPluginApexAppInstaller, resources/docker/oracle/bin/install-plugin-apex-app.sh; Core exports resources/db/apex/orac_apps/f1042.sql, f1043.sql, scaffold f10042.sql; plugin exports stay in plugins/<id>/apex.
Scopes/source/RAG: resources/db/schema/orac_core/{table,constraint_fk,constraint_uc,constraint_other,index,trigger}; orac_api views/TAPIs; orac_code knowledge_scope_api, knowledge_ingestion_api, knowledge_retrieval_api, rag_usage_privilege_api, rag_usage_authorization_api and views. CODE and PLUGIN knowledge_scope_validation_api bridge.
Python: src/orac_core/knowledge/{scope,models,capture,repository,retrieval}.py; src/model/plugin_knowledge_retrieval.py.
Drop Box: plugins/drop_box/{models,repository,service}.py and db/schema/{table,view,package_spec,package_body}.
Core controllers use includeAll, tables before constraints, API grants/views/specs/bodies, CODE view/body/grants. scripts/check_core_liquibase.py checks reachability/dependency closure.
Follow database-change-implementation skill and relevant governance; use apply_patch; no resets or destructive development DB testing.

Continue implementation, not another architecture review. Final handoff must clearly separate completed feature behaviour, tests actually run, and any validation that remains unavailable.
