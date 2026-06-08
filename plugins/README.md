# Orac Plugin Source Tree

The canonical plugin contract, lifecycle, policy, configuration, secrets,
database deployment, and audit documentation is in
[`docs/plugins.md`](../docs/plugins.md).

This directory contains implementation-adjacent plugin artefacts:

```text
plugins/<plugin-id>.json
plugins/<plugin-id>/
```

The manifest filename stem, manifest `plugin_id`, and implementation directory
must match. Discovery and routing use manifest metadata without importing plugin
implementation code.

Use [`plugins/_template/`](_template/) as the starting point for a new plugin.
Keep plugin-specific implementation notes in the plugin directory and avoid
duplicating the repository-level contract here.

Agent and maintainer requirements are defined in
[`docs/agent-guardrails/50-plugin-standards.md`](../docs/agent-guardrails/50-plugin-standards.md).
