# Plugin As A Service Remainder

## Current State

The manifest and schema groundwork for plugin-as-a-service is complete.

- Plugin manifests now use `schema_version: 2`.
- Plugins can declare `runtime.mode` as:
  - `on_demand`
  - `service`
  - `hybrid`
- `plugins/home_assistant.json` is the reference hybrid plugin.
- Home Assistant now declares:
  - on-demand entry point: `plugin:HomeAssistantPlugin`
  - service entry point: `plugin:HomeAssistantService`
  - service policy: auto-start, restart on failure, health check metadata
  - required database schema: `orac_ha`
  - database ownership marker: `"managed_by": "orac"`
- Routing excludes service-only plugins and plugins with missing required database schemas when `on_missing` is `warn_disable`.
- `orac_ha` now exists as a schema bundle, so Home Assistant can satisfy its declared database dependency.
- Tests cover manifest v2 validation, runtime modes, database metadata, and routing exclusion behavior.
- The manifest v2 work was committed as:
  - `1f6ebfc Add plugin manifest v2 runtime and database metadata`

## What Remains

### 1. Service Manager

Add an Orac-owned `PluginServiceManager`.

It should:

- start and stop service or hybrid plugin service entry points
- track service state such as starting, running, unhealthy, stopped, and failed
- apply restart policy
- apply shutdown timeout
- keep service orchestration owned by Orac, not by individual plugins

### 2. Service Contract

Define the runtime contract for service classes.

Likely methods:

- `start()`
- `stop(timeout_seconds)`
- optional `health()`

The implementation still needs a decision on whether services run as:

- threads
- subprocesses
- asyncio tasks

### 3. Home Assistant Service Implementation

Add `HomeAssistantService`.

It should own:

- Home Assistant websocket connection
- reconnect and backoff behavior
- periodic sync loop
- health reporting
- writes to the Home Assistant plugin schema

It should remain separate from the on-demand `HomeAssistantPlugin`.

### 4. Database Work

Finish validating the target `orac_ha` schema.

Remaining decisions/work:

- verify the renamed `orac_ha` artefacts
- add migration path metadata if existing deployments need a schema-owner move
- add install/check/version metadata so the manifest database dependency can be satisfied
- keep plugin-private storage separate from Orac core schemas

### 5. Runtime Integration

Hook service startup into Orac startup.

Startup should only happen after:

- manifest validation
- config validation
- entitlement/policy checks
- required database dependency checks

Orac should also expose service visibility through logs and, eventually, an admin/status surface.

## Summary

The manifest now knows how to describe service plugins.

Orac does not yet know how to run them.
