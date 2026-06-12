# Home Assistant Data Lifecycle

This document defines the implemented Home Assistant cache, resolution, and
control lifecycle. The `home_assistant` plugin is a registered hybrid plugin,
not a scaffold: its managed service synchronises Home Assistant data at startup
and handles approved resync, read-only area/sensor queries, and low-risk control
commands.

## Owned Data

The Home Assistant tables are cache/state tables, not audit tables:

| Object | Classification | Purpose |
| --- | --- | --- |
| `orac_ha.ha_areas` | Structural metadata cache | Home Assistant area registry data and aliases. |
| `orac_ha.ha_devices` | Structural metadata cache | Device registry data and effective area assignment. |
| `orac_ha.ha_entities` | Structural metadata cache | Entity registry data, names, domains, and device links. |
| `orac_ha.ha_states_current` | Current state cache | Latest synchronised entity state and attributes. |
| `orac_ha.ha_sync_runs` | Operational metadata | Structural/state sync status and row counts. |
| `orac_ha.device_aliases` | Persistent resolution data | Reviewed spoken aliases mapped to one or more entity IDs. |
| `orac_ha.ha_control_resolution_v` | Read-only resolution view | Enabled aliases joined to entity, device, area, area-alias, and current-state data. |

Device-control audit belongs to Orac's plugin audit/result persistence model,
not the Home Assistant cache tables.

## Ownership and Access

- `ORAC_HA` owns plugin tables, constraints, indexes, packages, and views.
- The managed service writes synchronised data through
  `orac_ha.ha_sync_api`.
- `ORAC_PLUGIN` receives only `SELECT` on
  `orac_ha.ha_control_resolution_v` for command resolution and area listing.
- Runtime code does not write aliases and does not receive direct table DML.
- Orac core retains plugin policy, provenance, timeout, and audit persistence.
- Home Assistant credentials remain in the encrypted plugin PAT vault and are
  never placed in conversational context or database cache rows.

There is deliberately no foreign key from `device_aliases.entity_id` to
`ha_entities.entity_id`. Structural synchronisation replaces entity rows;
persistent aliases must survive temporary disappearance or replacement of the
synced inventory.

## Synchronisation Model

The implemented service performs an initial pull refresh:

1. Validate plugin configuration and retrieve the access token from the PAT
   vault.
2. Fetch Home Assistant areas, devices, entities, and current states.
3. Replace structural cache rows through the approved sync package.
4. Replace current-state cache rows.
5. Record structural and state sync completion metadata.

The same path is available through `Sync devices`, `Resync devices`, and
`Resync Home Assistant`.

Websocket state updates and periodic reconciliation remain future work. Until
they are implemented, cached state reflects the last successful state sync.

## Read Paths

Target resolution and area listing read only
`orac_ha.ha_control_resolution_v`. The view combines:

- enabled persistent aliases
- entity IDs, object IDs, and entity names
- friendly names from current-state attributes
- device names
- effective entity/device area assignment
- Home Assistant area aliases
- current cached state for control resolution and diagnostics
- sensor device class and unit of measurement
- Home Assistant `last_changed` and `last_updated` timestamps

Area inventory and area-device listing remain fully local to the synchronised cache. Temperature and
humidity queries use the view only for stable entity, area, and alias metadata,
then fetch current values and timestamps directly from Home Assistant through
the read-only `/api/states` endpoint. They do not persist the fetched values or
present cached shadow readings as live. If a live request fails, any available
shadow value is returned only with explicit cached-data wording.

Temperature/humidity queries report update age and flag readings older than the
configured stale threshold. General non-climate state queries are not yet
implemented and must retain the same explicit freshness model when added.

## Control Path

Low-risk control follows this path:

1. Parse an allowlisted deterministic command.
2. Resolve enabled aliases, then exact entity/device names, then exact areas.
3. Reject whole-home, blocked-domain, unsupported, unknown, or ambiguous
   requests.
4. Map the request only to approved `light`, `switch`, or `scene` services.
5. Create an isolated Home Assistant REST client with a timeout shorter than
   the core plugin execution timeout.
6. POST to `/api/services/{domain}/{service}` with explicit entity IDs.
7. Return success only when Home Assistant confirms all requested entity IDs.
8. Close the ephemeral client and repository session.

The control path does not update `ha_states_current` optimistically. The next
state sync remains responsible for refreshing the cached state.

## Alias Lifecycle

Alias rows contain canonical lowercase alias text, a Home Assistant entity ID,
an enabled flag, timestamps, and a row version. The composite primary key is
`(alias_name, entity_id)`, allowing one alias to intentionally select several
entities.

Aliases are maintained only through reviewed DBA SQL or future deployment seed
scripts. The runtime does not insert aliases, infer aliases from conversation,
or expose alias-management commands.

## Failure and Freshness Behaviour

If credentials are missing or Home Assistant is offline:

- startup or on-demand sync reports a plugin-scoped failure;
- existing cache rows are not treated as newly refreshed;
- area listing may still use the last successfully synchronised inventory;
- control fails without broadening privileges or revealing credentials;
- Orac core remains available independently of the plugin failure.

Control responses distinguish confirmed success from unconfirmed or failed
execution. Router handling fails closed for matching mutation requests, so a
declined Home Assistant control command is not passed to the LLM for a fabricated
success response.

## Database Deployment

The Home Assistant schema payload is safely rerunnable so a changed payload
checksum can be deployed over an installed schema without dropping tables or
alias data. This is payload-local compatibility work. A general versioned and
idempotent plugin database migration mechanism remains a follow-up task.

## Future Work

- websocket state-change subscription
- periodic reconciliation and explicit stale-state metadata
- deterministic read-only state questions beyond temperature and humidity
- deployment-managed alias seed data or an approved alias administration UI
- general versioned plugin database migrations
