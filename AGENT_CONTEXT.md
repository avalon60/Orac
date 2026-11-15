# Orac Repository Agent Context

This durable context owns facts that cross Orac's web, core database, plugin,
APEX, deployment, and verification areas. Do not record credentials or secret
values here.

## Contents

- [Managed Areas](#managed-areas)
- [APEX Ownership](#apex-ownership)
- [Database Domains](#database-domains)
- [Liquibase Controller Topology](#liquibase-controller-topology)
- [Liquibase Runtime Contract](#liquibase-runtime-contract)
- [SQLcl Saved Connections](#sqlcl-saved-connections)
- [Plugin Context and Provenance](#plugin-context-and-provenance)
- [Cross-area Boundaries](#cross-area-boundaries)

## Managed Areas

| Area | Path | Context owner |
| --- | --- | --- |
| Browser application | `web/` | `web/AGENT_CONTEXT.md` |
| Core database schema | `resources/db/schema/` | `resources/db/schema/AGENT_CONTEXT.md` |
| Core APEX applications | `resources/db/apex/` | `resources/db/apex/AGENT_CONTEXT.md` |
| Plugin packages | `plugins/<plugin-code>/` | This root context plus plugin manifests and documentation |
| Plugin-owned APEX exports | `plugins/<plugin-code>/apex/` | This root context plus applicable plugin manifest |
| Core communications | `src/orac_core/communications/` | Transport-neutral request, response, event, and adapter contracts |

## APEX Ownership

Core workspace, parsing-schema, application-ID, export, import, navigation, and
theme facts belong in `resources/db/apex/AGENT_CONTEXT.md`. Database schema,
grant-direction, and controller facts remain in
`resources/db/schema/AGENT_CONTEXT.md`. Plugin-owned APEX applications remain
root-governed through their plugin manifests and documentation.

### Existing ORAC Workspace Applications

DEV installation status below reflects the APEX inventory verified on
06-Nov-2026, with the Chess correction verified on 08-Nov-2026. Repository declarations also reserve IDs for applications not
installed in that environment.

| Application ID | Application | Ownership | DEV installation | Repository evidence |
| --- | --- | --- | --- | --- |
| `1042` | Orac Administration | Core Orac | Installed | `resources/db/apex/AGENT_CONTEXT.md`; `resources/db/apex/orac_apps/f1042.sql` |
| `1043` | Plugin Control | Core Orac | Installed | `resources/db/apex/AGENT_CONTEXT.md`; `resources/db/apex/orac_apps/f1043.sql` |
| `10010` | Home Assistant Status | Plugin: `home_assistant` | Not installed; ID declared | `plugins/home_assistant.json`; `plugins/home_assistant/apex/f10010.sql` |
| `10020` | Drop Box Admin | Plugin: `drop_box` | Not installed; ID declared | `plugins/drop_box.json`; `plugins/drop_box/apex/f10020.sql` |
| `10030` | Orac Chess Explorer | Plugin: `orac_chess` | Installed; former application `100` removed | `plugins/orac_chess.json`; reservation below |
| `10042` | Plugin App Scaffold | Core scaffold | Installed | `resources/db/apex/AGENT_CONTEXT.md`; `resources/db/apex/orac_apps/f10042.sql` |

Core application details remain authoritative in
`resources/db/apex/AGENT_CONTEXT.md`; plugin declarations remain in their
manifests. The range configuration currently assigns `1000`–`1100` to Core and
`10000`–`10100` to Plugin in workspace `ORAC`. The existing core-owned scaffold
`10042` therefore has an ownership/range mismatch requiring separate resolution.
Treat its ID as occupied. Chess now uses its reserved Plugin-range ID below.

### Orac Chess Application ID Reservation

| Workspace | Domain | Inclusive range | Reserved application ID | Owner |
| --- | --- | --- | --- | --- |
| `ORAC` | `Plugin` | `10000`–`10100` | `10030` | `orac_chess` — Orac Chess Explorer |

The requester selected `10030` on 06-Nov-2026. The range is defined in
`docs/agent-guardrails/apex-app-id-ranges.csv`. Repository evidence includes
Home Assistant's `10010`, Drop Box's `10020`, the scaffold's `10042`, and the
Chess export's existing default application ID `10030`; no competing repository
claim for `10030` was found. No live APEX check was performed during this
allocation pass.

The display name changed to **Orac Chess Explorer** on 14-Nov-2026. The approved
APEX-only import updated the DEV application and host menu registration;
application ID and alias are unchanged.

The DEV installation verified on 08-Nov-2026 is application `10030`, alias
`ORAC_CHESS_ADMIN`, with parsing schema `ORAC_APX_PUB`. The manifest explicitly
declares `application_id: 10030`. The user-authorised correction removed former
application `100` through the APEX platform API and replaced its exact host
registration and receipt. Current APEX metadata, registry and navigation use
`10030`; plugin schema, data and Liquibase history were preserved. See
`plugins/orac_chess/docs/verification.md` for evidence and remaining UI checks.

## Database Domains

| Domain | Schemas | Ownership |
| --- | --- | --- |
| `orac` | `orac_core`, `orac_api`, `orac_code`, `orac_plugin`, `orac_apx_pub`, `orac` | Core data, controlled API, business code, plugin bridge, APEX access, and runtime access |
| `home_assistant` | `orac_ha` | Home Assistant plugin-private data and APIs |
| `drop_box` | `orac_dropbox` | Drop Box plugin-private configuration, jobs, and audit data |
| `orac_chess` | `orac_chess` | Chess plugin-private relational reference and instructional data |

Plugin schemas expose only approved entrypoints to `orac_plugin` or
`orac_apx_pub`. They do not receive direct access to `orac_core`.

## Liquibase Controller Topology

| Deployment | Entrypoint or runner | Controller | Ownership |
| --- | --- | --- | --- |
| Core Orac | `resources/db/schema/install.sql` or `install_orac.sql` | `resources/db/schema/productController.xml` | Includes the six core layer/access schema controllers in dependency order |
| Home Assistant | Core-owned plugin deployment runner | `plugins/home_assistant/db/liquibase/pluginController.xml` | Runs as `orac_ha` |
| Drop Box | Core-owned plugin deployment runner | `plugins/drop_box/db/liquibase/pluginController.xml` | Runs as `orac_dropbox` |
| Orac Chess | Core-owned plugin deployment runner | `plugins/orac_chess/db/liquibase/pluginController.xml` | Runs as `orac_chess` |

Plugin manifests declare the controller path and schema. Plugin controller
files own their ordered object-type includes.

## Liquibase Runtime Contract

- Core deployment uses SQLcl Liquibase with contexts and labels configured by
  `resources/db/liquibase/liquibase-core.properties`.
- Plugin deployment uses contexts `plugin,prod`, label `plugin`, and the
  packaged `db/liquibase/pluginController.xml`.
- Each plugin schema owns its own Liquibase history and lock tables.
- Runtime scripts obtain credentials from protected configuration; context
  records names and paths only.

## SQLcl Saved Connections

| Saved connection | Database user | Role | Purpose |
| --- | --- | --- | --- |
| `orac` | `ORAC` | `app` | Least-privileged internal runtime verification through the `orac` access schema |
| `orac_apx_pub` | `ORAC_APX_PUB` | `apex` | Objects and approved plugin surfaces visible to Orac APEX applications and clients |
| `orac-db` | `SYSTEM` | `admin` | Schema provisioning, cross-schema grants, invalid-object and container metadata, and installation diagnosis when elevated access is required |

Use the least-privileged role that can answer the question.

No owner-scoped SQLcl saved connections are currently available for the core
layer schemas or plugin-private schemas. `orac-service` and `orac-plugin` are
application-managed encrypted DSN credential entries selected by
`database.dsn_credential_entry` and
`database.plugin_dsn_credential_entry`. They are not SQLcl saved connections or
Oracle Net service aliases and are therefore not listed in this table.

## Plugin Context and Provenance

Plugins are provenance, not conversational roles or message types. Preserve
the host-owned projection contract:

- plugin tool results use role `tool` and message type `tool_result`
- plugin-sourced context uses role `system` and message type
  `context_injection`
- `plugin_id`, `tool_name`, `tool_call_id`, and applicable `meta` fields record
  plugin involvement separately
- Orac decides whether a plugin result enters active model context and produces
  the final user-facing response

## Cross-area Boundaries

- Browser source under `web` and core APEX exports are distinct application
  surfaces.
- Plugin-private data remains in plugin-owned schemas.
- Core owns routing, policy, confirmation, context mediation, provenance, and
  persistence.
- Every conversational transport enters `OracRequestProcessor` using canonical
  communications contracts. NDJSON, voice, and OpenAI-compatible shapes are
  adapters; none is an authentication, authorisation, or execution boundary.
- Caller restrictions only narrow Core authority: `None` adds no caller bound,
  while an empty capability or knowledge collection permits none. External
  session labels are namespaced to the authenticated principal.
- The OpenAI compatibility surface is reusable core code, not an HTTP listener.
  This tranche supports the documented text Chat Completions subset and model
  catalogue serialisation; deployable Open WebUI, Responses, and Codex routes
  remain later work.
- Do not infer a new schema domain, controller, privilege path, application id,
  port, or saved connection from directory names alone.
