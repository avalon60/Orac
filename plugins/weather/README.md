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
