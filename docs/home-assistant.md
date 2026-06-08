# Home Assistant

The Home Assistant plugin is a hybrid integration that synchronises Home
Assistant inventory into plugin-owned Oracle schemas and exposes a narrow
on-demand resync command. General plugin rules are documented in
[Plugins](plugins.md).

## Current Capability

Supported now:

- plugin configuration and scoped secret loading
- startup synchronisation of devices/entities and current states
- on-demand `home_assistant.resync`
- voice phrases such as `Resync Devices`
- shadow/current-state data for future queries and control

Not currently enabled:

- arbitrary device commands
- direct mutation of Home Assistant entities
- unconfirmed or policy-bypassing control

The data ownership and freshness model is detailed in
[Home Assistant Data Lifecycle](home-assistant-data-lifecycle.md).

## Configure Connection Details

Edit `plugins/home_assistant/plugin.ini` for non-secret values such as protocol,
host, port, TLS verification, and sync behavior. Do not place the token there.

The plugin manifest defines required settings and secret keys. Unresolved
template placeholders keep the plugin disabled.

## Create a Long-Lived Access Token

Create a Home Assistant long-lived access token with access to the required
inventory and state APIs, then store it in Orac's encrypted plugin PAT vault:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --set access_token
```

Inspection commands do not reveal the value:

```bash
bin/plugin-pat-mgr.sh --plugin home_assistant --list-expected
bin/plugin-pat-mgr.sh --plugin home_assistant --list-keys
bin/plugin-pat-mgr.sh --plugin home_assistant --check access_token
```

Use `--reveal` only for an explicit local diagnostic need. Never put the token
in logs, documentation, shell history, or normal configuration files.

## Database Schemas

Home Assistant data is owned by plugin schemas and deployed through the plugin
database deployment system. Orac runtime access goes through the controlled
plugin bridge and approved package APIs; it does not query plugin-owned tables
directly.

The data model distinguishes:

- structural inventory such as devices and entities
- current or shadow state
- synchronisation metadata and freshness

Missing Home Assistant credentials or an offline Home Assistant instance must
not prevent the core Orac runtime from starting. The plugin reports its own
degraded state and preserves the last successfully synchronised data where
appropriate.

## Synchronisation

The service performs its configured startup sync after plugin dependencies and
credentials are available. The on-demand command executes the same approved
service path:

```text
home_assistant.resync
```

Recognised voice phrases include `resync devices` and `resync home assistant`.
Successful execution responds that devices and entities were resynchronised.

Check the AI engine logs for accepted commands, structural/state sync results,
or connection failures:

```bash
bin/orac-ctl.sh logs ai
```

## Troubleshooting

### Plugin remains disabled

- Confirm `plugins/home_assistant.json` is enabled.
- Check required `plugin.ini` values for empty or template-placeholder values.
- Confirm the PAT vault contains `access_token`.
- Confirm plugin database deployment completed.

### Home Assistant is unreachable

- Verify protocol, host, port, and TLS settings.
- Test the Home Assistant API from the Orac host.
- Check whether certificate verification matches the deployment.
- Review AI engine logs for the plugin-scoped error.

### Resync fails

- Confirm the service plugin started successfully.
- Confirm the token remains valid and has appropriate access.
- Check database package/object deployment status.
- Review logs for whether structural or state synchronisation failed.

Device control remains disabled by design until policy, entitlements,
confirmation, command validation, and runtime implementation are complete.
