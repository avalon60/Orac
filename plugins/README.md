# Orac Plugin Source Tree

The canonical plugin contract, lifecycle, policy, configuration, secrets,
database deployment, and audit documentation is in
[`docs/plugins.md`](../docs/plugins.md).

This directory contains implementation-adjacent plugin artefacts:

```text
plugins/<plugin-id>.json
plugins/<plugin-id>/
plugins/<plugin-id>/resources/
```

The manifest filename stem, manifest `plugin_id`, and implementation directory
must match. Discovery and routing use manifest metadata without importing plugin
implementation code.

Plugins that declare `routing.interceptor` place immutable dialogue matching
metadata under `plugins/<plugin-id>/resources/intercept_meta.json`. Those rules
refer to manifest routes by `route_id`; the manifest remains authoritative for
capability and intent identity.

Use [`plugins/_template/`](_template/) as the starting point for a new plugin.
Keep plugin-specific implementation notes in the plugin directory and avoid
duplicating the repository-level contract here.

## Version Bumps

Each bundled plugin keeps a local `.bumpversion.cfg` in its implementation
directory. The top-level JSON manifest remains authoritative, and each config
must include the manifest plus any genuine current plugin-release version
occurrences that need to move with it. Do not include dependency constraints,
schema/API compatibility minimums, APEX export versions, host addresses, or
historical examples.

Run plugin bumps from the plugin implementation directory, for example:

```bash
cd plugins/weather
poetry run bump2version --allow-dirty --no-commit --no-tag patch
```

Use `--dry-run --verbose` first when checking a config. Bump2Version 1.0.1 may
still print VCS dry-run log lines while `commit` and `tag` are false; the
explicit `--no-commit --no-tag` switches keep the operator intent clear.
The bump configs are source-maintenance files and are excluded from plugin
archives and managed installs.

Agent and maintainer requirements are defined in
[`docs/agent-guardrails/50-plugin-standards.md`](../docs/agent-guardrails/50-plugin-standards.md).
