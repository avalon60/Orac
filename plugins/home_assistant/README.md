# Home Assistant Plugin Source

User and operator documentation is in
[`docs/home-assistant.md`](docs/home-assistant.md). The data ownership and
freshness contract is in
[`docs/home-assistant-data-lifecycle.md`](docs/home-assistant-data-lifecycle.md).

This directory contains the runtime implementation, plugin-local configuration,
and plugin-owned database assets for `home_assistant`.

The user guide includes the complete command reference for device control,
scene activation, area control, area listings, target resolution, aliases,
safety refusals, temperature/humidity queries, resynchronisation, and the
admin status surface for sync/API diagnostics.

Non-secret connection settings belong in `plugin.ini`. Store the long-lived
access token in Orac's encrypted plugin PAT vault:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --set access_token
```

Do not store the token in `plugin.ini` or other repository files.

## Declarative prompt interception

Deterministic pre-LLM interception rules are supplied by the plugin in
`resources/intercept_meta.json`. The plugin entry point loads and validates this
file through `plugin/intercept_metadata.py`. The metadata determines whether a
prompt is claimed; the existing Python parsers continue to extract and validate
domain-specific command parameters before execution. Named regular-expression captures and fixed rule `parameters` are retained in `InterceptMatch`, allowing metadata-defined sentence forms to supply structured values to the plugin handler.
