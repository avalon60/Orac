# Database Agent Instructions

This file contains database guidance for Orac schema assets under
`resources/db/schema`. It adapts the Codex SDK database topology to Orac's
existing repository layout.

Keep reusable database working rules here. Keep Orac-specific schema names,
schema responsibilities, folder mappings, consumer schemas, plugin bridge rules,
and local exceptions in the adjacent `AGENT_CONTEXT.md` file.

## Required Context Gate

Before changing, generating, moving, or reviewing database assets in this tree,
read the adjacent `AGENT_CONTEXT.md`.

If `AGENT_CONTEXT.md` is missing, halt and call out the missing file before
continuing with database work.

If `AGENT_CONTEXT.md` exists but does not describe a suitable mapping for the
relevant schema, namespace, consumer surface, or plugin bridge, halt and ask for
clarification before continuing.

Do not invent schema domains, layer schemas, object namespaces, access schemas,
plugin schemas, or folder-to-schema mappings from folder names alone.

## Database DDL Working Rules

Use the in-repo object-by-object DDL as the primary source for implementation
detail.

Do not start from monolithic deployment, generated export, or installer output
unless the task is specifically about that generated output or installer flow.

Follow the root `AGENTS.md` guardrail routing for database, PL/SQL, security,
plugins, context management, and table abbreviation rules.

## Schema Topology

Orac uses a least-privilege schema topology.

The normal Orac application database flow is:

```text
orac_core -> orac_api -> orac_code -> orac
                                  -> orac_apx_pub
                                  -> orac_plugin
```

General layer meanings:

- Core schemas own data structures.
- API schemas own controlled table access, API views, table triggers, and TAPIs.
- Code schemas own business logic, orchestration packages, and business views.
- Runtime and access schemas receive only approved grants needed for their
  documented role.
- Plugin-owned schemas own plugin-private artefacts and expose only approved
  entrypoints to the documented Orac plugin bridge schema.

Project-specific concrete schemas and exceptions must come from
`AGENT_CONTEXT.md`.

## How To Inspect A Database Change

When reviewing or implementing a database change:

1. Read `AGENT_CONTEXT.md`.
2. Start with the affected object file under the relevant schema folder.
3. Inspect neighbouring objects in the same folder to understand local
   conventions.
4. Inspect related constraints, indexes, grants, views, triggers, TAPIs,
   synonyms, and install ordering before proposing a design change.
5. Trace cross-layer changes where relevant:
   - `resources/db/schema/orac_core/...`
   - `resources/db/schema/orac_api/...`
   - `resources/db/schema/orac_code/...`
   - `resources/db/schema/orac/...`
   - `resources/db/schema/orac_apx_pub/...`
   - `resources/db/schema/orac_plugin/...` when present or explicitly in scope.

## Folder Meanings

Common schema bundle subdirectories include:

- `table/` = relational entities
- `constraint_pk/` = primary key constraints
- `constraint_fk/` = foreign key constraints
- `constraint_uc/` = unique constraints
- `constraint_other/` = other integrity constraints
- `index/` = indexes
- `comment/` = table and column comments
- `grant/` = grants from objects in the schema
- `privilege/` = incoming privileges needed by the schema
- `view/` = views owned by the schema
- `materialized_view/` = materialized views owned by the schema
- `trigger/` = triggers owned by the schema
- `package_spec/` = package specifications
- `package_body/` = package bodies
- `procedure/` = standalone procedures
- `function/` = standalone functions
- `sequence/` = sequences
- `synonym/` = private synonyms
- `seed_data/` = seed data scripts
- `pre_install/` = pre-install scripts
- `post_install/` = post-install scripts
- `orac_ws/` = APEX workspace export assets
- `orac_apps/` = APEX application export assets

Use the closest existing directory convention when a schema bundle has
additional object folders such as `type_spec`, `type_body`, `role`, `job`,
`schedule`, `context`, or `rest_module`.

## Judgement Rules

- Never create app-facing business objects in a runtime, consumer, access, or
  plugin bridge schema.
- Never grant direct access to `orac_core` from runtime, consumer, access,
  plugin bridge, or plugin-owned schemas.
- Never bypass `orac_api` or `orac_code` to make a change convenient.
- Never treat plugin-private storage as Orac-owned state.
- Never include `orac_ha` in normal database work unless the user explicitly
  requests Home Assistant or plugin-bound Home Assistant database assets.
- If the architecture contract and the DDL disagree, stop and flag the
  discrepancy.
