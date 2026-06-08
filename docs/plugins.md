# Plugins

Orac plugins add optional capabilities without taking ownership of core
orchestration, routing, persistence, security, or context management.

## Plugin Identity

A plugin is defined by matching filesystem artefacts:

```text
plugins/<plugin-id>.json
plugins/<plugin-id>/
```

The manifest filename stem, implementation directory, and manifest `plugin_id`
must match exactly. The manifest is the source of truth for discovery and
routing; implementation code is not imported during discovery.

## Manifest Contract

Required manifest fields include:

- `schema_version`
- `plugin_id`
- `name`
- `description`
- `version`
- `enabled`
- `capabilities`
- `entitlements`
- `runtime`

Optional fields include routing examples/entities, the Python `entry_point`,
execution policy, configuration declarations, secrets, and database payloads.

Routing text is derived only from routing-semantic metadata. Runtime,
configuration, database, and execution-policy data do not become prompt or
routing text.

## Runtime Modes

| Mode | Meaning |
|---|---|
| `on_demand` | Loaded for routed requests. |
| `service` | Managed as a long-running plugin service. |
| `hybrid` | Provides both service and on-demand behavior. |

Only enabled `on_demand` and `hybrid` plugins with satisfied dependencies are
eligible for the routing index. Service registration is handled separately by
the plugin service manager.

## Configuration and Secrets

Bundled source plugins may provide a configuration template at:

```text
plugins/<plugin-id>/plugin.ini.example
```

The installer creates mutable local configuration at
`~/.Orac/plugin_config/<plugin-id>/plugin.ini` and never overwrites an existing
file during reinstall or upgrade.

Plugins access configuration through the scoped runtime/service context. They
must not read arbitrary configuration files or another plugin's settings.

Secrets belong in the encrypted PAT vault at `~/.Orac/pat_vault.ini` and must
be declared by the manifest:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --set access_token
bin/plugin-pat-mgr.sh --plugin home_assistant --list-expected
bin/plugin-pat-mgr.sh --plugin home_assistant --check access_token
```

Do not put secrets in `plugin.ini`, `orac.ini`, shell history, or command-line
arguments. Plugin runtime contexts expose secrets only within the owning plugin
scope.

Unresolved template placeholders make a plugin ineligible for deployment,
routing, and service startup.

## Execution Policy and Confirmation

The optional `execution` manifest object classifies plugin risk before code is
loaded. Supported action classes include informational reads, external reads,
local or external mutation, device control, and privileged system actions.

Policy evaluates:

- action type
- required capabilities and entitlements
- whether confirmation is required
- whether execution is allowed by default
- scaffold/implementation status

Unknown or incompletely declared actions fail closed. Informational read-only
plugins may be allowed by default. Higher-risk actions require explicit policy
and, where declared, confirmation. See
[Plugin Execution Boundaries](plugin-execution-boundaries.md).

## Lifecycle and Services

Core runtime code owns discovery, dependency validation, service registration,
startup, shutdown, routing, execution policy, and provenance. Plugins receive
scoped contexts for the resources they are permitted to use.

Service and hybrid plugins must tolerate unavailable optional dependencies and
report failures without destabilising the core runtime. Plugin startup does not
grant authority to bypass confirmation, database, filesystem, network, or
context boundaries.

## Database Payloads

A plugin may declare owned database schemas and deployment assets. Plugin-owned
DDL remains under the plugin directory and is deployed through the approved
plugin database deployment path.

Plugins must not connect with core-schema owner credentials or bypass the
`orac_plugin` bridge. Runtime database access is restricted to declared,
approved APIs and grants. Database deployment status and audit data remain core
platform responsibilities.

## Audit and Provenance

Plugin-handled responses include provenance describing the plugin, capability,
action classification, and policy result. Invocation and audit persistence are
described in:

- [Plugin Audit Persistence](plugin-audit-persistence.md)
- [Plugin Audit Database/API Design](plugin-audit-db-api-design.md)

## Plugin Layout

Minimal layout:

```text
plugins/
  <plugin-id>.json
  <plugin-id>/
    README.md
    plugin.py
```

Add `resources/`, `db/schema/`, and plugin-local tests only when the plugin
requires them. Use `plugins/_template/` as the implementation starting point.

## Packaging And Installation

Plugins may be distributed as validated `.tar.gz` archives:

```text
manifest.json
plugin/
  plugin.py
  plugin.ini.example
  db/schema/
requirements.txt
README.md
```

Only `manifest.json` and `plugin/` are mandatory. The manifest is authoritative;
`requirements.txt`, when present, is a human-readable mirror and must match the
manifest dependency declarations.

```bash
bin/orac-plugin.sh package --source plugins/home_assistant --output dist/
bin/orac-plugin.sh install dist/orac-plugin-home_assistant-1.0.0.tar.gz
bin/orac-plugin.sh install --source plugins/home_assistant
bin/orac-plugin.sh install --bundled home_assistant
bin/orac-plugin.sh install --all
bin/orac-plugin.sh status home_assistant
bin/orac-plugin.sh check home_assistant
```

Installed versions live under `$ORAC_HOME/var/plugins/installed`. Mutable
configuration lives under `~/.Orac/plugin_config/<plugin-id>/plugin.ini`, and
encrypted secrets remain in `~/.Orac/pat_vault.ini`.

## Python Dependencies

Plugins declare their direct third-party dependencies in the manifest:

```json
"python_dependencies": [
  "requests>=2.32,<3"
]
```

The installer validates requirement syntax, rejects URLs, direct references,
local paths and pip options, installs into the active Orac environment using
`python -m pip`, and runs `python -m pip check`. Standard-library and Orac-owned
imports are not declared. Plugins must declare direct third-party imports even
when Orac core already supplies the package.

Installation validates configuration, required PAT-vault entries, dependencies,
database deployment and entry-point readiness. It does not start long-running
services or contact plugin external APIs. Only a successfully registered and
enabled installation is eligible for routing or service startup.

Repository-level implementation standards remain in
[`docs/agent-guardrails/50-plugin-standards.md`](agent-guardrails/50-plugin-standards.md).
