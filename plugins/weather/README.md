# Weather Plugin

This directory contains the runtime implementation for the `weather` plugin.

Current scope:

- current weather questions
- near-term hourly outlook questions
- short daily forecast summaries

The plugin currently uses Open-Meteo as its live data source through a narrow provider abstraction.

Current limitations:

- location handling is intentionally simple
- explicit places such as `London` or `Manchester` work best
- "where I am" style requests require a configured default location because this plugin does not geolocate the user
- the execution seam is deliberately modest and exists as a proving ground for the first real Orac plugin

The plugin does not use database connectivity in this pass.

## Declarative prompt interception

Deterministic pre-LLM interception rules are supplied by the plugin in
`resources/intercept_meta.json` and activated by the manifest
`routing.interceptor` entry. Orac core loads the resource through the bound
resource reader, validates each rule's `route_id` against the manifest routes,
and derives the selected capability and intent from the manifest.

Weather execution consumes `meta["plugin_route"]` arguments for the selected
route. The deprecated `can_handle()` method remains only as a temporary
compatibility delegate and is bypassed during normal migrated routing.
