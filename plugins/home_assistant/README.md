# Home Assistant Plugin Source

User and operator documentation is in
[`docs/home-assistant.md`](docs/home-assistant.md). The data ownership and
freshness contract is in
[`docs/home-assistant-data-lifecycle.md`](docs/home-assistant-data-lifecycle.md).

This directory contains the runtime implementation, plugin-local configuration,
and plugin-owned database assets for `home_assistant`.

The user guide includes the complete command reference for device control,
scene activation, area control, area listings, target resolution, aliases,
safety refusals, temperature/humidity queries, and resynchronisation.

Non-secret connection settings belong in `plugin.ini`. Store the long-lived
access token in Orac's encrypted plugin PAT vault:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --set access_token
```

Do not store the token in `plugin.ini` or other repository files.
