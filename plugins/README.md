# Orac Plugins

The `plugins/` directory contains Orac plugin source artefacts.

For plugin routing and discovery, Orac treats the top-level manifest files in this directory as the source of truth. A plugin is defined by a pair of filesystem artefacts:

- `plugins/<plugin-id>.json`
- `plugins/<plugin-id>/`

These names must match exactly:

- `plugin_id` in the manifest
- manifest filename stem
- implementation directory name

Example:

```text
plugins/weather.json
plugins/weather/
```

If those names do not match, the plugin is considered invalid for discovery/routing and will be skipped by the routing subsystem.

## Purpose Of The Plugins Directory

This directory is intended to hold:

- plugin manifests used for discovery and routing metadata
- plugin implementation code and plugin-local resources
- plugin-local tests and documentation where useful

This directory is not where plugin-routing cache files or in-memory search state live. Routing cache/index data is runtime state managed separately by Orac.

## Manifest And Directory Relationship

Each plugin has:

- a manifest at `plugins/<plugin-id>.json`
- a matching implementation directory at `plugins/<plugin-id>/`

The manifest is the source of truth for:

- plugin discovery
- plugin enablement
- routing-semantic metadata
- basic execution metadata such as `entry_point`

The implementation directory is for:

- Python code
- plugin-specific resources
- plugin-specific tests
- human-oriented plugin documentation

Orac must be able to discover and route to plugins from the manifest alone. Plugin code must not be imported merely to discover or route the plugin.
Orac must be able to discover, index, and route plugins using the manifest alone. Plugin implementation code must not be imported or inspected during discovery or routing.

## What The Manifest Is Used For

The current manifest schema is aligned with the plugin-routing v2 subsystem.

Required fields:

- `schema_version`
- `plugin_id`
- `name`
- `description`
- `version`
- `enabled`
- `capabilities`
- `entitlements`
- `runtime`

Optional fields:

- `entities`
- `examples`
- `entry_point`
- `execution`
- `configuration`
- `database`

Important distinctions:

- `description`, `capabilities`, `entities`, and `examples` are routing-semantic fields
- `entry_point` is execution metadata, not routing metadata
- `execution` is action-risk and provenance metadata, not routing text
- `runtime`, `configuration`, and `database` are runtime/dependency metadata, not routing text
- `version` is plugin/package metadata, not part of canonical routing text

The `entry_point` value is expected to reference a Python module and class within the matching plugin directory, for example `plugin:WeatherPlugin`. The exact loading and execution mechanism is intentionally deferred.

The current canonical routing text is derived from:

- `plugin_id`
- `name`
- `description`
- `capabilities`
- `entities` if present
- `examples` if present

The current canonical routing text does not include:

- `version`
- `entry_point`
- `execution`
- `runtime`
- `configuration`
- `database`

Only plugins with `"enabled": true`, `runtime.mode` of `on_demand` or `hybrid`, and satisfied runtime dependencies are included in the routing index.

## Execution Policy

Plugin manifests may declare first-pass execution policy metadata under the
optional `execution` object. This metadata lets Orac distinguish harmless
informational plugins from future mutation, device-control, filesystem,
external-service, or privileged actions before plugin code is imported.

Required `execution` fields:

- `action_type`: one of `informational_read_only`, `external_read`,
  `local_mutation`, `external_mutation`, `device_control`, or
  `privileged_system_action`
- `requires_confirmation`: whether the action must be confirmed before
  execution
- `allowed_by_default`: whether Orac may execute the plugin without an
  explicit allow policy

Optional `execution` fields:

- `capabilities`: the declared manifest capabilities covered by this policy
- `entitlements`: the declared manifest entitlements covered by this policy
- `scaffold`: marks an experimental or placeholder plugin as not executable
  for real control
- `notes`: human-readable policy context

Current behaviour:

- `informational_read_only` plugins with `allowed_by_default: true` may run.
- Higher-risk actions are denied or returned as requiring confirmation unless
  request policy metadata explicitly allows them.
- Unknown action types fail closed.
- Plugin-handled responses carry provenance metadata identifying the plugin,
  action type, and policy result.

The weather plugin is explicitly informational/read-only. The Home Assistant
plugin is marked scaffold-only and device-control-capable in intent, but real
control remains disabled until policy, entitlements, credentials and runtime
behaviour are complete.

## Required Vs Optional Files

Required for a valid plugin:

- `plugins/<plugin-id>.json`
- `plugins/<plugin-id>/`

Recommended for a minimal implementation:

- `plugins/<plugin-id>/README.md`
- `plugins/<plugin-id>/plugin.py`

Optional when needed:

- `plugins/<plugin-id>/__init__.py`
- `plugins/<plugin-id>/resources/`
- `plugins/<plugin-id>/tests/`

## Recommended Minimal Plugin Structure

For a simple plugin, prefer this layout:

```text
plugins/
  <plugin-id>.json
  <plugin-id>/
    README.md
    plugin.py
```

Guidance:

- keep the manifest concise and routing-oriented
- keep the implementation entry code in `plugin.py` unless there is a reason to split it
- use `README.md` to describe intent, dependencies, and local conventions for the plugin
- keep `examples` representative and varied
- do not let `examples` imply constraints or supported behaviours that the plugin does not actually provide

## Recommended Expanded Plugin Structure

For plugins that need more than a single module, prefer this layout:

```text
plugins/
  <plugin-id>.json
  <plugin-id>/
    __init__.py
    plugin.py
    README.md
    resources/
    tests/
```

Interpretation of each part:

- `__init__.py`
  Optional package marker if the plugin is implemented as a Python package
- `plugin.py`
  Main implementation module or stable home for the current `entry_point`
- `README.md`
  Developer-facing notes specific to the plugin
- `resources/`
  Plugin-local static artefacts such as schemas, prompt fragments, sample data, or other non-code resources
- `tests/`
  Plugin-local tests when the plugin grows large enough to justify them

Do not create subdirectories just to satisfy a template. Add them when the plugin actually needs them.

## Naming Conventions

Use these conventions consistently:

- `plugin_id` must match `^[a-z][a-z0-9_]*$`
- use lowercase snake_case for plugin ids and directory names
- keep filenames simple and predictable
- prefer `plugin.py` as the main implementation module for now

Examples of good ids:

- `weather`
- `home_assistant`
- `media_control`

Examples to avoid:

- `Weather`
- `media-control`
- `home assistant`

## Routing And Runtime Concerns

Routing cache and retrieval are runtime concerns, not plugin source artefacts.

That means:

- plugin manifests and code live under `plugins/`
- routing embeddings are cached by Orac in a runtime cache area
- the in-memory plugin intent index is built at runtime
- database vector search remains separate from plugin routing

Developers should not place routing cache files under plugin directories.

## Current Legacy/Transitional Artefacts

Some existing plugin-related files in this repository predate the current manifest-driven routing approach, for example:

- `plugins/home_assistant.ini`
- `plugins/home_assistant/manifest.ini`

These should be treated as legacy or transitional artefacts unless and until Orac explicitly adopts them for another purpose. They are not the source of truth for routing discovery in the current plugin-routing design.

## Illustrative Template

An illustrative, non-normative template is provided under:

```text
plugins/_template/
```

It exists to show a sensible starting point for new plugin implementation files. It is not itself a discoverable plugin because it does not have a matching top-level manifest.

## Intentionally Deferred

This pass does not define a full plugin framework. The following are intentionally deferred:

- plugin execution/loading conventions beyond the current `entry_point` idea
- database connectivity for plugins
- privilege models and security boundaries
- final plugin selection or router policy beyond candidate retrieval
- richer lifecycle management such as install, upgrade, disable, migrate, or unload operations
- a formal plugin SDK

Those concerns should be tackled later, once Orac moves beyond manifest-driven routing and begins defining runtime loading, execution, security, and database-connected plugins in more detail.
