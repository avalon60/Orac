# Home Assistant Architecture

## Boundary

Home Assistant owns hardware drivers, vendor integrations, entity registries,
states, supported features, and callable actions. Orac owns language routing,
semantic capability names, target resolution, policy, confirmation, parameter
validation, execution limits, and audit outcomes.

The runtime path is:

```text
natural-language intent
  -> Orac route and host execution policy
  -> discovered entity or composed Home Assistant device
  -> derived primitive capability
  -> validated Home Assistant action
  -> Home Assistant integration and hardware
```

No capability rule examines a device manufacturer or model. A device is a
stable Home Assistant device ID plus its member entities. Its capabilities are
the union of the bindings on those entities. Telemetry entities can therefore
coexist with control entities without requiring a device class in Orac.
Device names and areas come from the Home Assistant device registry, and an
entity inherits its device area when it has no entity-level area override.

## Discovery snapshot

`capabilities.py` defines immutable entity, state, action, binding, device, and
snapshot contracts. Structural sync obtains areas, devices, and entities from
the Home Assistant WebSocket registry commands. It also obtains the global
action catalogue and, where supported by the Home Assistant release,
target-specific action applicability. State sync obtains current state and
attributes from the REST API.

The candidate data is converted into one capability generation before commit.
The structural rows, state rows, sync-run results, and in-memory capability
generation are then published together. Any exception rolls back the complete
candidate transaction. Failure recording uses an autonomous database
transaction only after that rollback, so diagnostics cannot accidentally
commit an empty or partial replacement.

The generation digest includes entity structure, action schema fingerprints,
primitive parameter contracts, availability, and verification behaviour. It
therefore changes when an entity gains or loses a meaningful capability, even
when its entity ID remains stable.

## Initial primitive vocabulary

The initial vocabulary includes `read_state`, `turn_on`, `turn_off`,
`set_level`, `set_temperature`, `set_colour`, `set_colour_temperature`,
`open`, `close`, `stop`, `set_position`, `lock`, `unlock`, `play`, `pause`,
`set_volume`, and `trigger_action`. `set_value` and `select_option` are included
for Home Assistant helper-style domains. The enum is a versioned initial
vocabulary and may be extended without creating device model implementations.

Standard adapters currently recognise lights, switches, scenes, fans, climate
and water heaters, covers, valves, locks, media players, buttons, numbers, and
selects. A binding is emitted only when the required Home Assistant action is
present. Feature-specific light bindings additionally require compatible
`supported_color_modes`; ranges and options come from state attributes.

Unknown domains remain readable when Home Assistant provides state. When Home
Assistant supplies target-specific applicability, a service on an unfamiliar
integration is promoted automatically if its action name has one canonical
meaning and every parameter field required by that primitive is described.
Ambiguous and opaque services remain in the internal action catalogue for
diagnostics and later review; they are not exposed as arbitrary model-callable
methods. Adding a safe mapping for a new semantic operation changes a domain
adapter or canonical action-name rule, rather than adding vendor or model code.

## Invocation safety

`prepare_capability_operation` accepts an entity or device ID, a canonical
primitive, and primitive parameters. It resolves only bindings in the current
snapshot, enforces the configured entity-group limit, rejects extra fields,
validates numeric ranges and enumerations, and derives the Home Assistant
service data itself. A caller cannot supply a raw domain or service name.

The managed service exposes a paged `capability_inventory` command. It contains
semantic capability names and parameter contracts, plus composed device names,
areas, member entities, and capabilities for devices represented on the page.
It omits raw Home Assistant action IDs and excludes hidden or disabled entities.
Read and control capabilities are omitted when host policy denies that operation.
Page sizes and operation group limits are configuration defaults.

The plugin publishes matching model-tool schemas for semantic inventory and
execution. Execution accepts only a target ID, canonical capability, and the
parameters declared by that binding. The runtime replaces any caller-supplied
authority value with a host-created object carrying the authenticated
principal and trusted policy/confirmation outcome; plain JSON cannot imitate
that authority. Open, close, stop, position, lock, unlock, arbitrary trigger,
and helper mutation primitives require broker-trusted confirmation.

The existing light, switch, and scene routes remain compatible. After a
capability snapshot is available, those routes require the corresponding
derived binding before making a service call. This lets established commands
use the generic discovery contract while preserving their response and test
injection seams.

Orac's plugin router remains the host policy and confirmation boundary. The
plugin never exposes the complete Home Assistant service catalogue to a model.
Home Assistant `hidden_by` and `disabled_by` metadata is also enforced as an
inventory and resolution boundary. Discovering an action alone does not
authorise it.

## WebSocket transport

The maintained `websocket-client` 1.9 release line owns the WebSocket upgrade,
TLS, framing, socket timeout, send/receive, and close mechanics. Orac retains
Home Assistant protocol semantics: the authentication exchange, command type,
request ID matching, result/error interpretation, registry commands, and action
discovery.

`HomeAssistantClient(..., websocket_session=...)` remains the injection point
for protocol tests. HTTP `session` injection is unchanged. Direct transport
tests replace `websocket.create_connection`, so no test needs a network or a
physical Home Assistant instance.

## Testing new integrations

Capability tests use registry, state, global service, and target-service
fixtures. Representative fixtures should cover ordinary domains, multi-entity
devices, entities without device IDs, unavailable and hidden entities, unusual
ranges and options, services absent from one target, and unfamiliar platform,
manufacturer, or model values. The same fixture must derive the same semantic
result regardless of vendor metadata.

Physical ownership is therefore unnecessary. A regression fixture copied from
a redacted Home Assistant response is sufficient when a new integration
exposes an unusual but standards-compliant shape.
