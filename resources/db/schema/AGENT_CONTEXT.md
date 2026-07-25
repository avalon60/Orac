# Database Agent Context

This file contains Orac-specific database mappings for the generic guidance in
`resources/db/schema/AGENTS.md`.

## Table of Contents

- [Vocabulary](#vocabulary)
- [Core Orac Schema Domain](#core-orac-schema-domain)
- [Schema Responsibilities](#schema-responsibilities)
  - [`orac_core`](#orac_core)
  - [`orac_api`](#orac_api)
  - [`orac_code`](#orac_code)
  - [`orac`](#orac)
  - [`orac_apx_pub`](#orac_apx_pub)
  - [`orac_plugin`](#orac_plugin)
- [Object Namespaces And Folder Mappings](#object-namespaces-and-folder-mappings)
- [Application Context Ownership](#application-context-ownership)
- [Grant Direction](#grant-direction)
- [Core Liquibase Controller Topology](#core-liquibase-controller-topology)
- [Plugin Database Domains And Controllers](#plugin-database-domains-and-controllers)
- [Explicitly Out Of Normal Scope](#explicitly-out-of-normal-scope)
- [Project-Specific Invariants](#project-specific-invariants)

## Vocabulary

- Schema domain: the deployed database ownership family. For the core Orac
  application this is `orac`.
- Layer schema: a concrete Oracle schema inside the domain or access model.
- Object namespace: the folder and object naming prefix used by a schema bundle.
- Runtime schema: a least-privilege connection schema used by application code.
- Plugin bridge schema: a least-privilege schema used by Orac to call approved
  plugin database entrypoints.

## Core Orac Schema Domain

Current core Orac schema domain:

| Schema domain | Core schema | API schema | Code schema | Runtime schema | APEX/access schema | Plugin bridge schema | Purpose |
|---|---|---|---|---|---|---|---|
| `orac` | `orac_core` | `orac_api` | `orac_code` | `orac` | `orac_apx_pub` | `orac_plugin` | Core Orac database objects, internal runtime access, APEX access, and plugin database mediation. |

## Schema Responsibilities

### `orac_core`

`orac_core` owns core Orac data structures:

- tables
- indexes
- primary, unique, check, and foreign key constraints
- comments and seed data for core Orac metadata

`orac_core` must not contain business logic or application-facing access
surfaces. Runtime, APEX, plugin bridge, and plugin-owned schemas must not
receive direct access to `orac_core` tables.

### `orac_api`

`orac_api` owns controlled access to `orac_core`:

- pass-through API views
- table API packages
- API-layer triggers
- API-layer validation needed to protect table operations

`orac_api` may receive the minimum required grants from `orac_core`, with grant
option only where needed to expose approved API-layer objects.

### `orac_code`

`orac_code` owns Orac business logic:

- orchestration packages
- business rule packages
- business-facing views and materialized views
- higher-level database APIs used by Orac runtime, APEX, or plugin mediation

`orac_code` should read through `orac_api` views and modify data through
`orac_api` TAPI packages. It must not perform direct DML against `orac_core`
tables.

### `orac`

`orac` is the internal runtime connection schema for the core Orac Python stack.

It should receive only the grants needed by the Python runtime, normally to
approved `orac_code` packages and views. Selected `orac_api` access may be used
only when explicitly justified by the current design.

`orac` must not own core Orac business logic, must not own core Orac data
tables, and must not receive direct access to `orac_core` tables.

Some objects in `resources/db/schema/orac/synonym/` provide runtime or
compatibility synonyms. Treat those synonyms as access surfaces, not as object
ownership.

### `orac_apx_pub`

`orac_apx_pub` is the APEX and client-facing access schema.

It may receive selected grants to `orac_code` packages and views, and selected
`orac_api` views where APEX region behaviour requires direct API-layer access.
It must not receive direct access to `orac_core` tables.

### `orac_plugin`

`orac_plugin` is the plugin bridge schema between Orac and plugin-owned database
schemas.

Where a plugin requires its own database schema, the plugin-owned schema should
own its private tables, packages, views, and other artefacts. The plugin-owned
schema should grant only approved database-resident API entrypoints to
`orac_plugin`.

`orac_plugin` lets Orac call those approved plugin entrypoints without receiving
broad owner privileges in the plugin schema. It must not own plugin-private
tables and must not receive broad access to plugin internals.

## Object Namespaces And Folder Mappings

Current Orac schema bundle mappings:

| Folder | Owning schema | Object namespace | Purpose |
|---|---|---|---|
| `resources/db/schema/orac_core/` | `orac_core` | `orac` | Core Orac tables, constraints, indexes, seed data, and related schema-owned objects. |
| `resources/db/schema/orac_api/` | `orac_api` | `orac` | API views, table API packages, API triggers, incoming core privileges, and outgoing grants. |
| `resources/db/schema/orac_code/` | `orac_code` | `orac` | Business logic packages, business views, post-install assets, and outgoing grants. |
| `resources/db/schema/orac/` | `orac` | `orac` | Internal runtime connection schema synonyms and compatibility access surfaces for the core Python stack. |
| `resources/db/schema/orac_apx_pub/` | `orac_apx_pub` | `orac` | APEX/client-facing private synonyms and access surfaces. |
| `resources/db/schema/orac_plugin/` | `orac_plugin` | `orac` | Plugin bridge schema assets when present. |

The folder prefix does not by itself justify new privileges. Resolve ownership
and grant direction from this context and the relevant guardrails.

## Application Context Ownership

Core APEX workspace, application-ID, export, import, navigation, and theme
facts belong in `resources/db/apex/AGENT_CONTEXT.md`. Web application facts
belong in `web/AGENT_CONTEXT.md`. This database context retains ownership of
the `orac_apx_pub` schema, its least-privilege grant direction, synonyms, and
controller ordering.

## Grant Direction

Expected core Orac grant direction:

```text
orac_core -> orac_api -> orac_code -> orac
                                  -> orac_apx_pub
                                  -> orac_plugin
```

Expected plugin database grant direction:

```text
<plugin_schema> -> orac_plugin -> approved Orac runtime path
```

Rules:

- `orac_core` grants only the required object privileges to `orac_api`.
- `orac_api` grants only approved API views and program units to `orac_code`.
- `orac_code` grants only approved runtime APIs and business views to `orac`,
  `orac_apx_pub`, and `orac_plugin`.
- Plugin-owned schemas grant only approved entrypoints to `orac_plugin`.
- Do not grant direct `orac_core` table access to `orac`, `orac_apx_pub`,
  `orac_plugin`, or plugin-owned schemas.
- Do not grant broad plugin schema privileges to `orac_plugin`.

Physical placement follows the receiving-schema convention in this repository:

- Core-to-API privilege scripts live under
  `resources/db/schema/orac_api/privilege`, not under `orac_core/grant`.
- `orac_api/schemaController.xml` must install `privilege` before `view` so
  API pass-through views have the required `orac_core` access before they are
  created.
- Outgoing API grants live under `resources/db/schema/orac_api/grant`.
- Outgoing CODE grants live under `resources/db/schema/orac_code/grant`.
- Runtime and APEX private synonyms live under the receiving schema's
  `synonym` directory.

## Core Liquibase Controller Topology

The supported core SQLcl entrypoints are:

- `resources/db/schema/install.sql`
- `resources/db/schema/install_orac.sql`

Both invoke `resources/db/schema/productController.xml`. The production
controller includes schema controllers in this order:

1. `orac_core/schemaController.xml`
2. `orac_api/schemaController.xml`
3. `orac_code/schemaController.xml`
4. `orac_plugin/schemaController.xml`
5. `orac_apx_pub/schemaController.xml`
6. `orac/schemaController.xml`

The order is architectural. Core objects precede API access, business code,
the plugin bridge, APEX access, and the internal runtime access surface.

Core deployment uses SQLcl Liquibase with
`resources/db/liquibase/liquibase-core.properties`. Do not record database
passwords or wallet contents in this context.

## Plugin Database Domains And Controllers

Active plugin-owned database domains are:

| Plugin domain | Owning schema | Manifest | Liquibase controller | Purpose |
|---|---|---|---|---|
| `home_assistant` | `orac_ha` | `plugins/home_assistant.json` | `plugins/home_assistant/db/liquibase/pluginController.xml` | Home Assistant plugin-private integration state and APIs. |
| `drop_box` | `orac_dropbox` | `plugins/drop_box.json` | `plugins/drop_box/db/liquibase/pluginController.xml` | Drop Box plugin-private configuration, ingestion jobs, and audit data. |

The Core-owned plugin deployment runner reads the declared schema and
controller from the plugin package. Plugin deployment uses contexts
`plugin,prod` and label `plugin`. Each plugin schema owns its own Liquibase
history and lock tables.

Plugin controllers own their ordered object-type includes. Plugin-private
schemas expose only approved entrypoints to `orac_plugin` and approved APEX
surfaces to `orac_apx_pub`; they do not receive direct access to `orac_core`.

## Explicitly Out Of Normal Scope

`orac_ha` and `orac_dropbox` are active plugin-owned schemas. Do not include
them in core Orac database work, grant changes, or topology changes unless the
task explicitly covers the owning plugin or its approved bridge.

When either plugin domain is in scope, apply the plugin, database, Liquibase,
and security guardrails before changing it.

## Project-Specific Invariants

- Preserve the documented schema ownership boundaries.
- Keep Orac core runtime access through `orac` least-privilege grants.
- Keep plugin-private data inside plugin-owned schemas.
- Use `orac_plugin` as the controlled bridge to approved plugin database APIs.
- Do not infer new access schemas, plugin schemas, public synonyms, or broad
  grants from existing folder names.
- Check `docs/agent-guardrails/table-abbreviations.csv` before creating or
  renaming tables, constraints, indexes, triggers, TAPI packages, or object
  names derived from table abbreviations.
