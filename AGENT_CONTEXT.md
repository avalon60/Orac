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

## APEX Ownership

Core workspace, parsing-schema, application-ID, export, import, navigation, and
theme facts belong in `resources/db/apex/AGENT_CONTEXT.md`. Database schema,
grant-direction, and controller facts remain in
`resources/db/schema/AGENT_CONTEXT.md`. Plugin-owned APEX applications remain
root-governed through their plugin manifests and documentation.

## Database Domains

| Domain | Schemas | Ownership |
| --- | --- | --- |
| `orac` | `orac_core`, `orac_api`, `orac_code`, `orac_plugin`, `orac_apx_pub`, `orac` | Core data, controlled API, business code, plugin bridge, APEX access, and runtime access |
| `home_assistant` | `orac_ha` | Home Assistant plugin-private data and APIs |
| `drop_box` | `orac_dropbox` | Drop Box plugin-private configuration, jobs, and audit data |

Plugin schemas expose only approved entrypoints to `orac_plugin` or
`orac_apx_pub`. They do not receive direct access to `orac_core`.

## Liquibase Controller Topology

| Deployment | Entrypoint or runner | Controller | Ownership |
| --- | --- | --- | --- |
| Core Orac | `resources/db/schema/install.sql` or `install_orac.sql` | `resources/db/schema/productController.xml` | Includes the six core layer/access schema controllers in dependency order |
| Home Assistant | Core-owned plugin deployment runner | `plugins/home_assistant/db/liquibase/pluginController.xml` | Runs as `orac_ha` |
| Drop Box | Core-owned plugin deployment runner | `plugins/drop_box/db/liquibase/pluginController.xml` | Runs as `orac_dropbox` |

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

| Saved connection | Role | Purpose |
| --- | --- | --- |
| `orac` | `app` | Least-privileged internal Orac verification |
| `orac-db` | `admin` | Cross-schema grants, invalid objects, container metadata, and installation diagnosis |
| `orac_apx_pub` | `apex` | Objects visible to Orac APEX applications |

Use the least-privileged role that can answer the question.

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
- Do not infer a new schema domain, controller, privilege path, application id,
  port, or saved connection from directory names alone.
