# Home Assistant Plugin Source

User and operator documentation is in
[`docs/home-assistant.md`](docs/home-assistant.md). The data ownership and
freshness contract is in
[`docs/home-assistant-data-lifecycle.md`](docs/home-assistant-data-lifecycle.md).

This source directory contains the implementation, plugin-local configuration
template, and plugin-owned database assets for `home_assistant`. The normal Orac
runtime loads the activated installed snapshot recorded in the plugin registry,
not this source directory directly.

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
`resources/intercept_meta.json` and activated by the manifest
`routing.interceptor` entry. Orac core loads the resource through the bound
resource reader, validates each rule's `route_id` against the manifest routes,
and derives the selected capability and intent from the manifest.

Home Assistant execution dispatches from `meta["plugin_route"]` and keeps
plugin-owned safety validation, target/domain semantics, service calls, and
response formatting. The deprecated `can_handle()` method remains only as a
temporary compatibility delegate and is bypassed during normal migrated
routing.
