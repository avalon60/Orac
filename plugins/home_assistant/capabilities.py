"""Derive generic Orac capabilities from Home Assistant metadata."""
# Author: Clive Bostock
# Date: 11-Sep-2026
# Description: Models discovered entities, actions, and primitive bindings.

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import hashlib
import json
from typing import Any, Iterable, Mapping


class PrimitiveCapability(StrEnum):
    """Initial extensible vocabulary understood by Orac's semantic layer."""

    READ_STATE = "read_state"
    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"
    SET_LEVEL = "set_level"
    SET_TEMPERATURE = "set_temperature"
    SET_COLOUR = "set_colour"
    SET_COLOUR_TEMPERATURE = "set_colour_temperature"
    OPEN = "open"
    CLOSE = "close"
    STOP = "stop"
    SET_POSITION = "set_position"
    LOCK = "lock"
    UNLOCK = "unlock"
    PLAY = "play"
    PAUSE = "pause"
    SET_VOLUME = "set_volume"
    TRIGGER_ACTION = "trigger_action"
    SET_VALUE = "set_value"
    SELECT_OPTION = "select_option"


@dataclass(frozen=True, slots=True)
class EntityDescriptor:
    """Stable Home Assistant entity identity and structural metadata."""

    entity_id: str
    domain: str
    device_id: str | None
    area_id: str | None
    name: str
    platform: str | None = None
    device_class: str | None = None
    entity_category: str | None = None
    disabled: bool = False
    hidden: bool = False


@dataclass(frozen=True, slots=True)
class StateSnapshot:
    """One observed Home Assistant entity state."""

    entity_id: str
    state: str | None
    attributes: Mapping[str, Any] = field(default_factory=dict)
    last_changed: str | None = None
    last_updated: str | None = None

    @property
    def available(self) -> bool:
        """Return whether Home Assistant reports a usable current value."""
        return str(self.state or "").lower() not in {"", "unknown", "unavailable"}


@dataclass(frozen=True, slots=True)
class ActionDescriptor:
    """Normalised Home Assistant service/action description."""

    action_id: str
    domain: str
    service: str
    fields: Mapping[str, Any]
    target: Mapping[str, Any]
    schema_fingerprint: str


@dataclass(frozen=True, slots=True)
class CapabilityBinding:
    """Primitive capability bound to one validated Home Assistant action."""

    entity_id: str
    primitive: PrimitiveCapability
    action_id: str | None
    parameters: Mapping[str, Any]
    evidence: tuple[str, ...]
    available: bool
    verification: str


@dataclass(frozen=True, slots=True)
class DeviceDescriptor:
    """A discovered device composed from its member entities."""

    device_id: str
    name: str
    area_id: str | None
    entity_ids: tuple[str, ...]
    capabilities: Mapping[PrimitiveCapability, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class CapabilitySnapshot:
    """Coherent derived entity, action, binding, and device generation."""

    entities: Mapping[str, EntityDescriptor]
    states: Mapping[str, StateSnapshot]
    actions: Mapping[str, ActionDescriptor]
    bindings: Mapping[str, tuple[CapabilityBinding, ...]]
    devices: Mapping[str, DeviceDescriptor]
    generation: str

    @property
    def unmapped_action_count(self) -> int:
        """Return discovered HA actions not promoted to semantic bindings."""
        mapped = {
            binding.action_id
            for values in self.bindings.values()
            for binding in values
            if binding.action_id is not None
        }
        return len(set(self.actions) - mapped)


@dataclass(frozen=True, slots=True)
class PreparedCapabilityOperation:
    """Validated primitive invocation ready for host policy evaluation."""

    primitive: PrimitiveCapability
    target_id: str
    entity_ids: tuple[str, ...]
    action_id: str | None
    service_data: Mapping[str, Any]
    verification: str


def model_tool_schemas() -> tuple[dict[str, Any], ...]:
    """Return bounded model schemas containing no raw HA service selector."""
    return (
        {
            "type": "function",
            "function": {
                "name": "home_assistant_capabilities",
                "description": "List visible Home Assistant entities and semantic capabilities.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "offset": {"type": "integer", "minimum": 0},
                        "limit": {"type": "integer", "minimum": 1},
                    },
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "home_assistant_execute",
                "description": "Request one semantic capability for a discovered target.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_id": {"type": "string"},
                        "capability": {
                            "type": "string",
                            "enum": [item.value for item in PrimitiveCapability],
                        },
                        "parameters": {
                            "type": "object",
                            "additionalProperties": True,
                        },
                    },
                    "required": ["target_id", "capability"],
                    "additionalProperties": False,
                },
            },
        },
    )


_STANDARD_ACTIONS: dict[str, tuple[tuple[PrimitiveCapability, str, str], ...]] = {
    "light": (
        (PrimitiveCapability.TURN_ON, "turn_on", "state_on"),
        (PrimitiveCapability.TURN_OFF, "turn_off", "state_off"),
        (PrimitiveCapability.SET_LEVEL, "turn_on", "brightness"),
        (PrimitiveCapability.SET_COLOUR, "turn_on", "colour"),
        (
            PrimitiveCapability.SET_COLOUR_TEMPERATURE,
            "turn_on",
            "colour_temperature",
        ),
    ),
    "switch": (
        (PrimitiveCapability.TURN_ON, "turn_on", "state_on"),
        (PrimitiveCapability.TURN_OFF, "turn_off", "state_off"),
    ),
    "scene": ((PrimitiveCapability.TRIGGER_ACTION, "turn_on", "unverified"),),
    "fan": (
        (PrimitiveCapability.TURN_ON, "turn_on", "state_on"),
        (PrimitiveCapability.TURN_OFF, "turn_off", "state_off"),
        (PrimitiveCapability.SET_LEVEL, "set_percentage", "percentage"),
    ),
    "climate": (
        (PrimitiveCapability.SET_TEMPERATURE, "set_temperature", "temperature"),
    ),
    "water_heater": (
        (PrimitiveCapability.SET_TEMPERATURE, "set_temperature", "temperature"),
    ),
    "cover": (
        (PrimitiveCapability.OPEN, "open_cover", "opening"),
        (PrimitiveCapability.CLOSE, "close_cover", "closing"),
        (PrimitiveCapability.STOP, "stop_cover", "unverified"),
        (PrimitiveCapability.SET_POSITION, "set_cover_position", "position"),
    ),
    "valve": (
        (PrimitiveCapability.OPEN, "open_valve", "opening"),
        (PrimitiveCapability.CLOSE, "close_valve", "closing"),
        (PrimitiveCapability.STOP, "stop_valve", "unverified"),
        (PrimitiveCapability.SET_POSITION, "set_valve_position", "position"),
    ),
    "lock": (
        (PrimitiveCapability.LOCK, "lock", "locked"),
        (PrimitiveCapability.UNLOCK, "unlock", "unlocked"),
    ),
    "media_player": (
        (PrimitiveCapability.PLAY, "media_play", "playing"),
        (PrimitiveCapability.PAUSE, "media_pause", "paused"),
        (PrimitiveCapability.SET_VOLUME, "volume_set", "volume"),
    ),
    "button": ((PrimitiveCapability.TRIGGER_ACTION, "press", "unverified"),),
    "input_button": ((PrimitiveCapability.TRIGGER_ACTION, "press", "unverified"),),
    "number": ((PrimitiveCapability.SET_VALUE, "set_value", "value"),),
    "input_number": ((PrimitiveCapability.SET_VALUE, "set_value", "value"),),
    "select": ((PrimitiveCapability.SELECT_OPTION, "select_option", "option"),),
    "input_select": ((PrimitiveCapability.SELECT_OPTION, "select_option", "option"),),
}

_DYNAMIC_ACTION_NAMES: dict[str, tuple[PrimitiveCapability, str]] = {
    "turn_on": (PrimitiveCapability.TURN_ON, "state_on"),
    "turn_off": (PrimitiveCapability.TURN_OFF, "state_off"),
    "set_percentage": (PrimitiveCapability.SET_LEVEL, "percentage"),
    "set_temperature": (PrimitiveCapability.SET_TEMPERATURE, "temperature"),
    "open": (PrimitiveCapability.OPEN, "opening"),
    "open_cover": (PrimitiveCapability.OPEN, "opening"),
    "open_valve": (PrimitiveCapability.OPEN, "opening"),
    "close": (PrimitiveCapability.CLOSE, "closing"),
    "close_cover": (PrimitiveCapability.CLOSE, "closing"),
    "close_valve": (PrimitiveCapability.CLOSE, "closing"),
    "stop": (PrimitiveCapability.STOP, "unverified"),
    "stop_cover": (PrimitiveCapability.STOP, "unverified"),
    "stop_valve": (PrimitiveCapability.STOP, "unverified"),
    "set_position": (PrimitiveCapability.SET_POSITION, "position"),
    "set_cover_position": (PrimitiveCapability.SET_POSITION, "position"),
    "set_valve_position": (PrimitiveCapability.SET_POSITION, "position"),
    "lock": (PrimitiveCapability.LOCK, "locked"),
    "unlock": (PrimitiveCapability.UNLOCK, "unlocked"),
    "media_play": (PrimitiveCapability.PLAY, "playing"),
    "media_pause": (PrimitiveCapability.PAUSE, "paused"),
    "volume_set": (PrimitiveCapability.SET_VOLUME, "volume"),
    "press": (PrimitiveCapability.TRIGGER_ACTION, "unverified"),
    "set_value": (PrimitiveCapability.SET_VALUE, "value"),
    "select_option": (PrimitiveCapability.SELECT_OPTION, "option"),
}

_PRIMITIVE_SERVICE_FIELDS: dict[PrimitiveCapability, str] = {
    PrimitiveCapability.SET_LEVEL: "percentage",
    PrimitiveCapability.SET_TEMPERATURE: "temperature",
    PrimitiveCapability.SET_POSITION: "position",
    PrimitiveCapability.SET_VOLUME: "volume_level",
    PrimitiveCapability.SET_VALUE: "value",
    PrimitiveCapability.SELECT_OPTION: "option",
}

# Home Assistant domain feature masks are used only when target-specific action
# discovery is unavailable. Target discovery remains the stronger evidence.
_FEATURE_MASKS: dict[tuple[str, PrimitiveCapability], int] = {
    ("fan", PrimitiveCapability.SET_LEVEL): 1,
    ("climate", PrimitiveCapability.SET_TEMPERATURE): 1,
    ("water_heater", PrimitiveCapability.SET_TEMPERATURE): 1,
    ("cover", PrimitiveCapability.OPEN): 1,
    ("cover", PrimitiveCapability.CLOSE): 2,
    ("cover", PrimitiveCapability.SET_POSITION): 4,
    ("cover", PrimitiveCapability.STOP): 8,
    ("valve", PrimitiveCapability.OPEN): 1,
    ("valve", PrimitiveCapability.CLOSE): 2,
    ("valve", PrimitiveCapability.SET_POSITION): 4,
    ("valve", PrimitiveCapability.STOP): 8,
    ("media_player", PrimitiveCapability.PAUSE): 1,
    ("media_player", PrimitiveCapability.SET_VOLUME): 4,
    ("media_player", PrimitiveCapability.PLAY): 16384,
}


def normalise_actions(
    services: Mapping[str, Any],
) -> dict[str, ActionDescriptor]:
    """Normalise Home Assistant's nested service-description catalogue."""
    actions: dict[str, ActionDescriptor] = {}
    for domain, domain_services in services.items():
        if not isinstance(domain_services, Mapping):
            continue
        for service, description in domain_services.items():
            details = description if isinstance(description, Mapping) else {}
            action_id = f"{domain}.{service}".lower()
            canonical = json.dumps(details, sort_keys=True, default=str, separators=(",", ":"))
            actions[action_id] = ActionDescriptor(
                action_id=action_id,
                domain=str(domain).lower(),
                service=str(service).lower(),
                fields=_mapping(details.get("fields")),
                target=_mapping(details.get("target")),
                schema_fingerprint=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            )
    return actions


def derive_capability_snapshot(
    entities: Iterable[Mapping[str, Any]],
    states: Iterable[Mapping[str, Any]],
    services: Mapping[str, Any],
    *,
    services_by_entity: Mapping[str, Iterable[str]] | None = None,
    devices: Iterable[Mapping[str, Any]] = (),
) -> CapabilitySnapshot:
    """Derive generic primitive bindings without manufacturer/model dispatch."""
    state_map: dict[str, StateSnapshot] = {}
    for item in states:
        if not item.get("entity_id"):
            continue
        snapshot = _state(item)
        state_map[snapshot.entity_id] = snapshot
    device_rows = tuple(devices)
    device_areas = {
        str(item.get("id") or "").strip(): _optional(item.get("area_id"))
        for item in device_rows
        if item.get("id")
    }
    entity_map = _entities(entities, state_map, device_areas=device_areas)
    actions = normalise_actions(services)
    service_index = {
        key.lower(): frozenset(str(value).lower() for value in values)
        for key, values in (services_by_entity or {}).items()
    }
    bindings = {
        entity_id: _bindings_for(entity, state_map.get(entity_id), actions, service_index)
        for entity_id, entity in entity_map.items()
    }
    return _build_snapshot(
        entity_map,
        state_map,
        actions,
        bindings,
        device_metadata=device_rows,
    )


def update_capability_state(
    snapshot: CapabilitySnapshot,
    raw_state: Mapping[str, Any],
) -> CapabilitySnapshot:
    """Return a new coherent generation after one HA state-change event."""
    state = _state(raw_state)
    if not state.entity_id:
        raise ValueError("Home Assistant state event is missing entity_id.")
    states = dict(snapshot.states)
    states[state.entity_id] = state
    entities = dict(snapshot.entities)
    if state.entity_id not in entities:
        entities.update(_entities((), {state.entity_id: state}))
    bindings = dict(snapshot.bindings)
    prior_actions = frozenset(
        binding.action_id
        for binding in bindings.get(state.entity_id, ())
        if binding.action_id
    )
    service_index = (
        {state.entity_id: prior_actions}
        if prior_actions
        else {}
    )
    bindings[state.entity_id] = _bindings_for(
        entities[state.entity_id],
        state,
        snapshot.actions,
        service_index,
    )
    return _build_snapshot(
        entities,
        states,
        snapshot.actions,
        bindings,
        device_metadata=snapshot.devices,
    )


def _build_snapshot(
    entity_map: Mapping[str, EntityDescriptor],
    state_map: Mapping[str, StateSnapshot],
    actions: Mapping[str, ActionDescriptor],
    bindings: Mapping[str, tuple[CapabilityBinding, ...]],
    *,
    device_metadata: Iterable[Mapping[str, Any]] | Mapping[str, DeviceDescriptor] = (),
) -> CapabilitySnapshot:
    """Build one immutable snapshot and content-derived generation ID."""
    devices = _devices(entity_map, bindings, device_metadata)
    material = {
        "entities": sorted(
            (
                entity_id,
                value.domain,
                value.device_id,
                value.area_id,
                value.platform,
                value.device_class,
                value.entity_category,
                value.disabled,
                value.hidden,
            )
            for entity_id, value in entity_map.items()
        ),
        "actions": sorted((key, value.schema_fingerprint) for key, value in actions.items()),
        "bindings": sorted(
            (
                entity_id,
                binding.primitive.value,
                binding.action_id,
                json.dumps(binding.parameters, sort_keys=True, default=str),
                binding.available,
                binding.verification,
            )
            for entity_id, values in bindings.items()
            for binding in values
        ),
        "devices": sorted(
            (device_id, device.name, device.area_id, device.entity_ids)
            for device_id, device in devices.items()
        ),
    }
    generation = hashlib.sha256(
        json.dumps(material, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return CapabilitySnapshot(
        dict(entity_map),
        dict(state_map),
        dict(actions),
        dict(bindings),
        devices,
        generation,
    )


def prepare_capability_operation(
    snapshot: CapabilitySnapshot,
    target_id: str,
    primitive: PrimitiveCapability | str,
    parameters: Mapping[str, Any] | None = None,
    *,
    max_entities: int = 25,
) -> tuple[PreparedCapabilityOperation, ...]:
    """Resolve and validate an entity/device primitive without calling HA.

    The returned operations are safe inputs to a host policy decision. Service
    names always come from the derived snapshot, never from model supplied text.
    """
    try:
        capability = PrimitiveCapability(str(primitive))
    except ValueError as exc:
        raise ValueError(f"Unknown Home Assistant primitive '{primitive}'.") from exc
    target = str(target_id or "").strip().lower()
    if target in snapshot.entities:
        entity_ids = (target,)
    elif target in snapshot.devices:
        entity_ids = snapshot.devices[target].capabilities.get(capability, ())
    else:
        raise ValueError(f"Unknown Home Assistant target '{target_id}'.")
    if not entity_ids:
        raise ValueError(
            f"Home Assistant target '{target_id}' does not expose '{capability.value}'."
        )
    if len(entity_ids) > max(1, int(max_entities)):
        raise ValueError("Home Assistant target exceeds the configured entity-group limit.")

    supplied = dict(parameters or {})
    prepared: list[PreparedCapabilityOperation] = []
    for entity_id in entity_ids:
        matches = [
            binding
            for binding in snapshot.bindings.get(entity_id, ())
            if binding.primitive == capability and binding.available
        ]
        if len(matches) != 1:
            raise ValueError(
                f"Home Assistant entity '{entity_id}' does not expose one unambiguous "
                f"'{capability.value}' binding."
            )
        binding = matches[0]
        service_data = _service_data(entity_id, capability, supplied, binding.parameters)
        prepared.append(
            PreparedCapabilityOperation(
                capability,
                target,
                (entity_id,),
                binding.action_id,
                service_data,
                binding.verification,
            )
        )
    return tuple(prepared)


def _service_data(
    entity_id: str,
    primitive: PrimitiveCapability,
    supplied: Mapping[str, Any],
    schema: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Validate primitive parameters and translate them to HA service fields."""
    expected = set(schema)
    extras = set(supplied) - expected
    missing = expected - set(supplied)
    if extras or missing:
        detail = ", ".join(sorted(extras or missing))
        reason = "unexpected" if extras else "missing"
        raise ValueError(f"Home Assistant capability parameters are {reason}: {detail}.")
    for name, value_schema in schema.items():
        _validate_parameter(name, supplied[name], _mapping(value_schema))

    if primitive == PrimitiveCapability.SET_LEVEL:
        field = "brightness_pct" if entity_id.startswith("light.") else "percentage"
        return {field: supplied["percent"]}
    if primitive == PrimitiveCapability.SET_TEMPERATURE:
        return {"temperature": supplied["temperature"]}
    if primitive == PrimitiveCapability.SET_COLOUR:
        return {"rgb_color": list(supplied["rgb"])}
    if primitive == PrimitiveCapability.SET_COLOUR_TEMPERATURE:
        return {"color_temp_kelvin": supplied["kelvin"]}
    if primitive == PrimitiveCapability.SET_POSITION:
        field = "position"
        return {field: supplied["percent"]}
    if primitive == PrimitiveCapability.SET_VOLUME:
        return {"volume_level": float(supplied["percent"]) / 100.0}
    if primitive == PrimitiveCapability.SET_VALUE:
        return {"value": supplied["value"]}
    if primitive == PrimitiveCapability.SELECT_OPTION:
        return {"option": supplied["option"]}
    return {}


def _validate_parameter(name: str, value: Any, schema: Mapping[str, Any]) -> None:
    """Validate one value against the small emitted capability schema subset."""
    if schema.get("type") == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Home Assistant capability parameter '{name}' must be numeric.")
        if "minimum" in schema and value < schema["minimum"]:
            raise ValueError(f"Home Assistant capability parameter '{name}' is below minimum.")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValueError(f"Home Assistant capability parameter '{name}' is above maximum.")
    elif schema.get("type") == "string":
        if not isinstance(value, str):
            raise ValueError(f"Home Assistant capability parameter '{name}' must be text.")
        if schema.get("enum") and value not in schema["enum"]:
            raise ValueError(f"Home Assistant capability parameter '{name}' is not an option.")
    elif schema.get("type") == "array":
        if not isinstance(value, (list, tuple)):
            raise ValueError(f"Home Assistant capability parameter '{name}' must be an array.")
        if len(value) < int(schema.get("minItems", 0)) or len(value) > int(
            schema.get("maxItems", len(value))
        ):
            raise ValueError(f"Home Assistant capability parameter '{name}' has invalid length.")
        item_schema = _mapping(schema.get("items"))
        for index, item in enumerate(value):
            _validate_parameter(f"{name}[{index}]", item, item_schema)


def _entities(
    entities: Iterable[Mapping[str, Any]],
    states: Mapping[str, StateSnapshot],
    *,
    device_areas: Mapping[str, str | None] | None = None,
) -> dict[str, EntityDescriptor]:
    inherited_areas = device_areas or {}
    result: dict[str, EntityDescriptor] = {}
    for raw in entities:
        entity_id = str(raw.get("entity_id") or "").lower()
        if "." not in entity_id:
            continue
        state = states.get(entity_id)
        attributes = state.attributes if state else {}
        device_id = _optional(raw.get("device_id"))
        result[entity_id] = EntityDescriptor(
            entity_id=entity_id,
            domain=entity_id.partition(".")[0],
            device_id=device_id,
            area_id=_optional(raw.get("area_id")) or inherited_areas.get(device_id or ""),
            name=str(raw.get("name") or attributes.get("friendly_name") or entity_id),
            platform=_optional(raw.get("platform")),
            device_class=_optional(attributes.get("device_class")),
            entity_category=_optional(raw.get("entity_category")),
            disabled=bool(raw.get("disabled_by")),
            hidden=bool(raw.get("hidden_by")),
        )
    for entity_id, state in states.items():
        if entity_id not in result:
            result[entity_id] = EntityDescriptor(
                entity_id=entity_id,
                domain=entity_id.partition(".")[0],
                device_id=None,
                area_id=None,
                name=str(state.attributes.get("friendly_name") or entity_id),
                device_class=_optional(state.attributes.get("device_class")),
            )
    return result


def _bindings_for(
    entity: EntityDescriptor,
    state: StateSnapshot | None,
    actions: Mapping[str, ActionDescriptor],
    service_index: Mapping[str, frozenset[str]],
) -> tuple[CapabilityBinding, ...]:
    available = bool(state and state.available and not entity.disabled)
    bindings = [
        CapabilityBinding(
            entity.entity_id,
            PrimitiveCapability.READ_STATE,
            None,
            {},
            ("current_state",),
            bool(state and not entity.disabled),
            "read",
        )
    ]
    applicable = service_index.get(entity.entity_id)
    standard_action_ids: set[str] = set()
    mapped_primitives: set[PrimitiveCapability] = {PrimitiveCapability.READ_STATE}
    for primitive, service, verification in _STANDARD_ACTIONS.get(entity.domain, ()):
        action_id = f"{entity.domain}.{service}"
        standard_action_ids.add(action_id)
        if action_id not in actions:
            continue
        if applicable is not None and action_id not in applicable:
            continue
        if applicable is None and not _supported_by_feature_metadata(
            entity.domain,
            primitive,
            state,
        ):
            continue
        parameters = _parameters(primitive, state)
        if parameters is None:
            continue
        bindings.append(
            CapabilityBinding(
                entity.entity_id,
                primitive,
                action_id,
                parameters,
                ("service_catalogue", "entity_domain", *(_feature_evidence(primitive, state))),
                available,
                verification,
            )
        )
        mapped_primitives.add(primitive)

    if applicable is not None:
        dynamic_candidates: dict[
            PrimitiveCapability,
            list[tuple[str, Mapping[str, Any], str]],
        ] = {}
        for action_id in sorted(applicable):
            if action_id in standard_action_ids or action_id not in actions:
                continue
            action = actions[action_id]
            dynamic = _DYNAMIC_ACTION_NAMES.get(action.service)
            if dynamic is None:
                continue
            primitive, verification = dynamic
            if primitive in mapped_primitives:
                continue
            parameters = _parameters(primitive, state)
            if parameters is None or not _dynamic_action_has_required_fields(
                primitive,
                action,
            ):
                continue
            dynamic_candidates.setdefault(primitive, []).append(
                (action_id, parameters, verification)
            )
        for primitive, candidates in dynamic_candidates.items():
            if len(candidates) != 1:
                continue
            action_id, parameters, verification = candidates[0]
            bindings.append(
                CapabilityBinding(
                    entity.entity_id,
                    primitive,
                    action_id,
                    parameters,
                    ("target_service_applicability", "canonical_action_name"),
                    available,
                    verification,
                )
            )
    return tuple(bindings)


def _dynamic_action_has_required_fields(
    primitive: PrimitiveCapability,
    action: ActionDescriptor,
) -> bool:
    """Require described fields before mapping parameterised custom actions."""
    required_field = _PRIMITIVE_SERVICE_FIELDS.get(primitive)
    return required_field is None or required_field in action.fields


def _supported_by_feature_metadata(
    domain: str,
    primitive: PrimitiveCapability,
    state: StateSnapshot | None,
) -> bool:
    """Use HA supported_features conservatively when target discovery is absent."""
    required_mask = _FEATURE_MASKS.get((domain, primitive))
    if required_mask is None:
        return True
    supported = state.attributes.get("supported_features") if state else None
    if isinstance(supported, bool) or not isinstance(supported, int):
        return False
    return bool(supported & required_mask)


def _parameters(
    primitive: PrimitiveCapability,
    state: StateSnapshot | None,
) -> Mapping[str, Any] | None:
    attributes = state.attributes if state else {}
    modes = {str(item).lower() for item in attributes.get("supported_color_modes") or ()}
    if primitive == PrimitiveCapability.SET_LEVEL:
        if state and state.entity_id.startswith("light.") and not modes & {
            "brightness", "color_temp", "hs", "rgb", "rgbw", "rgbww", "xy"
        }:
            return None
        return {"percent": {"type": "number", "minimum": 0, "maximum": 100}}
    if primitive == PrimitiveCapability.SET_COLOUR and not modes & {
        "hs", "rgb", "rgbw", "rgbww", "xy"
    }:
        return None
    if primitive == PrimitiveCapability.SET_COLOUR_TEMPERATURE and "color_temp" not in modes:
        return None
    if primitive == PrimitiveCapability.SET_TEMPERATURE:
        return _bounded_number(attributes, "min_temp", "max_temp", "target_temp_step", "temperature")
    if primitive == PrimitiveCapability.SET_POSITION:
        return {"percent": {"type": "number", "minimum": 0, "maximum": 100}}
    if primitive == PrimitiveCapability.SET_VOLUME:
        return {"percent": {"type": "number", "minimum": 0, "maximum": 100}}
    if primitive == PrimitiveCapability.SET_VALUE:
        return _bounded_number(attributes, "min", "max", "step", "value")
    if primitive == PrimitiveCapability.SELECT_OPTION:
        options = [str(item) for item in attributes.get("options") or ()]
        return {"option": {"type": "string", "enum": options}} if options else None
    if primitive == PrimitiveCapability.SET_COLOUR:
        return {
            "rgb": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {"type": "number", "minimum": 0, "maximum": 255},
            }
        }
    if primitive == PrimitiveCapability.SET_COLOUR_TEMPERATURE:
        return _bounded_number(
            attributes,
            "min_color_temp_kelvin",
            "max_color_temp_kelvin",
            None,
            "kelvin",
        )
    return {}


def _bounded_number(
    attributes: Mapping[str, Any],
    minimum_key: str,
    maximum_key: str,
    step_key: str | None,
    name: str,
) -> Mapping[str, Any] | None:
    minimum, maximum = attributes.get(minimum_key), attributes.get(maximum_key)
    if not isinstance(minimum, (int, float)) or not isinstance(maximum, (int, float)):
        return None
    schema: dict[str, Any] = {"type": "number", "minimum": minimum, "maximum": maximum}
    if step_key and isinstance(attributes.get(step_key), (int, float)):
        schema["multipleOf"] = attributes[step_key]
    return {name: schema}


def _feature_evidence(
    primitive: PrimitiveCapability,
    state: StateSnapshot | None,
) -> tuple[str, ...]:
    attributes = state.attributes if state else {}
    evidence: list[str] = []
    if "supported_features" in attributes:
        evidence.append(f"supported_features={attributes['supported_features']}")
    if "supported_color_modes" in attributes:
        evidence.append("supported_color_modes")
    return tuple(evidence)


def _devices(
    entities: Mapping[str, EntityDescriptor],
    bindings: Mapping[str, tuple[CapabilityBinding, ...]],
    metadata: Iterable[Mapping[str, Any]] | Mapping[str, DeviceDescriptor] = (),
) -> dict[str, DeviceDescriptor]:
    details: dict[str, tuple[str, str | None]] = {}
    if isinstance(metadata, Mapping):
        details = {
            device_id: (device.name, device.area_id)
            for device_id, device in metadata.items()
            if isinstance(device, DeviceDescriptor)
        }
    else:
        for item in metadata:
            device_id = str(item.get("id") or "").strip()
            if not device_id:
                continue
            details[device_id] = (
                str(item.get("name_by_user") or item.get("name") or device_id),
                _optional(item.get("area_id")),
            )
    members: dict[str, list[str]] = {}
    for entity in entities.values():
        if entity.device_id:
            members.setdefault(entity.device_id, []).append(entity.entity_id)
    result: dict[str, DeviceDescriptor] = {}
    for device_id, entity_ids in members.items():
        by_capability: dict[PrimitiveCapability, list[str]] = {}
        for entity_id in entity_ids:
            for binding in bindings.get(entity_id, ()):
                by_capability.setdefault(binding.primitive, []).append(entity_id)
        default_area = next(
            (entities[entity_id].area_id for entity_id in entity_ids if entities[entity_id].area_id),
            None,
        )
        name, area_id = details.get(device_id, (device_id, default_area))
        result[device_id] = DeviceDescriptor(
            device_id=device_id,
            name=name,
            area_id=area_id or default_area,
            entity_ids=tuple(sorted(entity_ids)),
            capabilities={
                key: tuple(sorted(set(value)))
                for key, value in by_capability.items()
            },
        )
    return result


def _state(raw: Mapping[str, Any]) -> StateSnapshot:
    return StateSnapshot(
        entity_id=str(raw.get("entity_id") or "").lower(),
        state=_optional(raw.get("state")),
        attributes=_mapping(raw.get("attributes")),
        last_changed=_optional(raw.get("last_changed")),
        last_updated=_optional(raw.get("last_updated")),
    )


def _mapping(value: Any) -> Mapping[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _optional(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
