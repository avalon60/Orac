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
`resources/intercept_meta.json`. The plugin entry point loads and validates this
file through `plugin/intercept_metadata.py`. The metadata determines whether a
prompt is claimed; the existing Python parsers continue to extract and validate
domain-specific command parameters before execution. Named regular-expression captures and fixed rule `parameters` are retained in `InterceptMatch`, allowing metadata-defined sentence forms to supply structured values to the plugin handler.
