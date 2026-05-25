# Home Assistant Data Lifecycle

This note defines the intended Home Assistant data lifecycle before Orac
implements real Home Assistant state query or device control. It is design
documentation only. It does not enable websocket integration, table population,
or device control.

## Current State

The `home_assistant` plugin is scaffold-only. Its manifest declares service and
hybrid capabilities, but `execution.scaffold` is true, so policy denies runtime
control before plugin code can perform actions.

The current service implementation is a placeholder. It starts under Orac
service supervision and deliberately does not connect to Home Assistant.

The `ORAC_HA` database objects exist as schema assets only. They are not
populated by the runtime yet.

## Table Classification

The current HA tables should be treated as cache/state tables, not audit tables:

| Table | Classification | Purpose |
| --- | --- | --- |
| `orac_ha.ha_areas` | Structural metadata cache | Cached Home Assistant area registry data. |
| `orac_ha.ha_devices` | Structural metadata cache | Cached Home Assistant device registry data. |
| `orac_ha.ha_entities` | Structural metadata cache | Cached Home Assistant entity registry data. |
| `orac_ha.ha_states_current` | Current state cache | Latest known entity state and attributes. |

These tables are not sufficient for device-control audit. Device-control audit
belongs in the plugin audit/result persistence model described in
`docs/plugin-audit-persistence.md`.

## Ownership

The future Home Assistant service plugin should own HA table population through
an Orac-approved API boundary. It must not write directly to protected core
tables or bypass plugin policy.

Expected responsibilities:

- Orac plugin service lifecycle supervises the HA service process/thread.
- HA service discovers registry/state data only after configuration and
  credentials are validated.
- HA service writes HA cache/state through a controlled data access layer.
- Orac core owns policy, confirmation, provenance, and audit persistence.
- User-facing state query and device control remain disabled until these
  boundaries are implemented and tested.

## Population Model

The intended population model is both pull and websocket, but staged:

1. Initial pull refresh:
   - fetch areas, devices, entities, and current states from Home Assistant;
   - upsert structural cache tables;
   - upsert `ha_states_current`;
   - record refresh timestamps and source metadata.
2. Websocket event stream:
   - subscribe to HA state changes after the initial pull is complete;
   - update `ha_states_current` for state-change events;
   - trigger structural refresh when registry-related changes are detected.
3. Periodic reconciliation:
   - periodically re-pull registry and current state snapshots;
   - reconcile missed websocket events after disconnects;
   - mark stale rows when HA has not reported them within the freshness window.

No part of this pass implements those behaviours.

## Freshness

State query must not present cached HA data as live unless freshness is known.

The future runtime should track:

- last successful registry refresh;
- last successful current-state snapshot;
- last websocket event time;
- HA connection status;
- per-row `updated_on`;
- HA-native timestamps such as `last_changed`, `last_updated`, and
  `last_reported`.

A state query should include freshness metadata internally and should degrade
safely when data is stale. If state is stale or HA is offline, Orac should say
that the cached state may be stale rather than implying live certainty.

## Version Compatibility

The HA manifest already declares an `orac_ha` schema requirement with a minimum
version and disabled version check. Before runtime population starts, Orac needs
a real compatibility check that verifies:

- required HA tables exist;
- required columns and constraints exist;
- JSON columns accept the expected payload shape;
- plugin manifest schema version is compatible with database object version;
- runtime service version is compatible with cache/state schema version.

If the check fails, the HA service should be disabled with clear diagnostics.
It must not partially populate tables or enable device control.

## Missing Credentials

If Home Assistant credentials are missing:

- the service should not connect to HA;
- HA cache/state refresh should not run;
- state query should report unavailable configuration;
- device control must remain denied;
- audit should record configuration failure once durable audit exists.

The access token should remain in the configured environment variable and must
not be stored in conversation history, plugin provenance, or audit details.

## Offline Home Assistant

If Home Assistant is offline:

- websocket subscription should not be attempted indefinitely without backoff;
- cache/state tables should remain read-only from the failed refresh attempt;
- stale status should be visible to state-query code;
- user-facing state query should distinguish stale cached state from live state;
- device control must remain denied.

## State Query Path

The intended first state-query implementation should read cached Orac HA tables,
not call live HA directly in the user request path. Reasons:

- state query remains fast and bounded;
- stale/offline semantics are explicit;
- query behaviour can be audited and tested;
- prompt handling does not gain direct network authority;
- HA credentials stay inside the supervised service layer.

Live HA calls may still be used by the supervised service for refresh and
reconciliation, not by conversational request handling.

## Why Device Control Remains Disabled

Device control must remain disabled until all of the following exist:

- reliable HA state query and freshness semantics;
- trusted confirmation UX/protocol;
- broker-backed confirmation state persisted or otherwise auditable;
- credential validation and secret handling;
- user/plugin entitlement checks;
- durable plugin audit/result persistence;
- idempotency and target validation for device actions;
- safety rules for locks, doors, alarms, appliances, scenes, and automations;
- failure handling for partial HA success/failure;
- tests proving denied/scaffold/unknown/timeout/error paths remain safe.

Until then, Home Assistant should remain scaffold-only even if a broker
confirmation exists.

## Recommended Next Step

The next implementation step should be a database/API design pass for plugin
audit/result persistence, followed by a read-only HA cache population pass. The
read-only pass should populate structural metadata and current state under
service supervision, with state query still returning only clearly marked cached
results. Device control should remain out of scope.
