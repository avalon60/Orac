# Orac Architecture QA Update 1

Date: 25-May-2026

## Executive Summary

This was a review-only reconciliation pass against the original
`architecture-qa-results.md` audit and the current repository state. No code,
DDL, or documentation was modified as part of the review pass itself.

The remediation work has materially improved the architecture. Provider behavior
is now concentrated in `ProviderRegistry`, plugin policy runs before import,
Home Assistant remains scaffold-only, service lifecycle is wired, and plugin
provenance reaches response and assistant-turn metadata.

The main remaining pressure point is still `src/controller/orac.py`, which is
4,236 lines and continues to own request orchestration, persistence, streaming,
plugin handoff, and response shaping. `PluginExecutionService` is a useful seam,
but it is currently mostly a delegate to `PluginRouter`; it is not yet the owner
of execution lifecycle, durable audit, or hard isolation.

## Updated Top 10 Status

| # | Original issue | Current status |
| --- | --- | --- |
| 1 | Protocol/schema/live stream drift | Mostly resolved. Contract tests exist and stream/TTS frames validate fail-closed, but `_build_response` still logs validation failure and returns anyway in `src/controller/orac.py`. |
| 2 | Protocol validation fail-open | Mostly resolved. Missing protocol validator now fails closed unless explicit env override is used. |
| 3 | Core orchestrator too broad | Still open. `Orac` remains the primary pressure point. |
| 4 | Provider-specific logic leaks into core | Mostly resolved. Provider behavior moved to `src/model/provider_registry.py`; `Orac` still owns provider selection and startup wiring. |
| 5 | Streaming abstraction unclear per provider | Mostly resolved. Provider capabilities now describe native/fallback streaming. |
| 6 | Service/hybrid plugin lifecycle not wired | Mostly resolved. `PluginServiceManager` is wired and supervises service/hybrid plugins, but still in-process and cooperative. |
| 7 | Plugin execution lacks policy/provenance boundary | Mostly resolved. Policy, confirmation, timeout, failure, and provenance exist; durable audit and hard cancellation do not. |
| 8 | Home Assistant advertised active placeholder capabilities | Mostly resolved. HA is enabled as a hybrid service, but `execution.scaffold=true` blocks runtime action before import. |
| 9 | Voice local loop oversized state machine | Partially resolved. `VoiceTurnController` improves the boundary, but much of the turn state machine was moved rather than decomposed. |
| 10 | Tests overfit private internals | Partially resolved. Contract tests improved coverage, but many tests still use `Orac.__new__` and private methods. This is acceptable short-term but constrains refactors. |

## Newly Discovered Architectural Risks

- Plugin timeout is cooperative only. `PluginRouter` returns timed-out
  provenance, but the worker thread can continue running after timeout. This is
  acceptable for current safe/scaffold plugins, not for future device control or
  mutation.
- `PluginExecutionService` is thin: it delegates directly to router. It is a
  good future seam, not yet the owner of execution lifecycle.
- Final response protocol validation is not fail-closed, unlike stream events.
- HA service auto-starts as a placeholder because the manifest is hybrid/auto,
  but the implementation deliberately does not connect to HA. This is safe now;
  future HA service work must not treat service start as permission to
  connect/control.

## Stale Documentation / Code Mismatches

- `docs/plugin-audit-db-api-design.md` still says the abbreviation entries are
  for a "future object-by-object DDL/API pass"; those assets now exist.
- `docs/plugin-audit-db-api-design.md` still lists "Create object-by-object DDL"
  as deferred, but the files are present.
- `docs/home-assistant-data-lifecycle.md` recommends a DB/API design pass as the
  next step; that appears superseded by the current plugin audit DB/API assets.
- No stale `plg_aud_evt` references were found. Current abbreviation use is
  `plg_audevt`.

## Boundary Assessment

### Core Controller

Improved around providers, plugins, and voice, but still too broad.
`src/controller/orac.py` remains the central pressure point and still combines
request handling, protocol validation, persistence, model selection, plugin
handoff, stream emission, response construction, voice routing, and pruning.

The next extraction should avoid another thin relocation. It should target a
real responsibility boundary, most likely plugin audit lifecycle recording or
response/protocol envelope construction.

### Provider Runtime

Coherent. `ProviderRegistry` owns provider capabilities, connector factory, and
provider-specific availability checks. Provider-specific behavior has genuinely
moved out of `Orac` for the current Ollama/LM Studio scope.

Remaining coupling is mostly provider selection and startup configuration inside
`Orac`, which is acceptable for now.

### Plugin Execution

The execution boundary is safer than the original audit: policy is evaluated
before import, scaffold/unknown/confirmation-required paths can avoid plugin
code, and core-owned provenance overrides plugin-supplied provenance.

The boundary is not complete. `PluginExecutionService` delegates to
`PluginRouter`; durable audit, lifecycle event persistence, hard cancellation,
and process isolation are still deferred.

### Plugin Service Lifecycle

`PluginServiceManager` now registers service/hybrid manifests, starts auto
services, supervises stop/shutdown, tracks health, and owns service threads.

The lifecycle remains in-process and cooperative. Scheduled/long-running service
timeouts do not provide hard termination. Database dependency checks are light
schema-root checks, not installed-version verification.

### Confirmation Broker

The broker is a good trusted seam relative to request metadata. It issues
confirmation ids, enforces expiry, validates plugin/action/capability matches,
and consumes confirmations once.

It is intentionally insufficient for real risky actions because it is in-memory
and does not yet bind confirmations to durable audit rows, user identity,
session identity, target payload, or protocol-level confirmation UX.

### Voice Runtime

`VoiceTurnController` improved the boundary by isolating one voice turn from the
local voice loop. The local loop still owns activation, capture, STT/TTS setup,
and display bridge setup.

The controller is still a large turn-level state machine. It mixes protocol
frame parsing, playback timing, barge-in cancellation, display state, console
output, and stale-frame filtering. This is a useful first extraction, not a
final decomposition.

### Home Assistant

Home Assistant remains safely scaffold-only. The manifest declares hybrid
service capability and Home Assistant capabilities, but `execution.scaffold` is
true. Runtime policy denies control before plugin import, and scaffold denial
overrides request metadata and broker confirmation.

The service implementation is a placeholder and deliberately does not open a
websocket or populate tables.

### DB/API Persistence

Plugin audit DB/API assets are now present as object-by-object files:

- `orac_core.plugin_invocations`
- `orac_core.plugin_audit_events`
- `orac_api` views and TAPIs
- `orac_code.plugin_audit_api`
- grants for `orac_code` and `orac`

The design is ready for a runtime integration pass, pending database
verification. Runtime plugin execution is not yet wired to
`orac_code.plugin_audit_api`.

Home Assistant tables remain cache/state tables, not audit tables:

- `orac_ha.ha_areas`
- `orac_ha.ha_devices`
- `orac_ha.ha_entities`
- `orac_ha.ha_states_current`

### Protocol / Display

Protocol/display alignment is improved by schema-backed contract tests and
runtime validation. Stream and TTS frames fail closed on validation failure.

The main residual inconsistency is final non-streaming response construction:
`_build_response` catches validation errors, logs them, and returns the frame
anyway.

## Recommended Next Sequence

1. Reconcile stale docs wording around plugin audit DB/API and HA next steps.
2. Add database verification for plugin audit objects, grants, constraints, and
   package validity.
3. Add a small runtime-facing plugin audit adapter around
   `orac_code.plugin_audit_api`, but do not call it from plugin code.
4. Wire audit recording into the plugin execution path through
   `PluginExecutionService`, including denied, confirmation-required, failed,
   timed-out, and completed outcomes.
5. Only after durable audit exists, implement read-only HA cache population
   under `PluginServiceManager`.
6. Later, split `VoiceTurnController` into protocol parsing,
   playback/cancellation, and display-state concerns.
7. Defer broader `Orac.handle_request` extraction until plugin audit wiring
   clarifies the next stable seam.

## Do Not Do Yet

- Do not enable real HA device control.
- Do not add HA websocket integration.
- Do not add live HA state query in the user request path.
- Do not let plugins write audit tables directly.
- Do not rely on the in-memory confirmation broker for real risky actions.
- Do not treat plugin timeout as execution cancellation for mutations.
- Do not remove scaffold protection from HA.

## Validation

Command run:

```bash
poetry run python -m unittest discover -s tests
```

Result:

```text
Ran 343 tests in 2.545s
OK (skipped=2)
```
