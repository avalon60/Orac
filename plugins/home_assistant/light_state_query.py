"""Deterministic Home Assistant live light-state parsing and rendering."""
# Author: Clive Bostock
# Date: 12-Jun-2026
# Description: Parses light read-back queries and renders live Home Assistant state.

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .color_description import describe_rgb_color
from .light_control import light_target_display_name


class LightStateQueryError(ValueError):
    """Raised when a light-state query cannot be parsed or rendered safely."""

    def __init__(self, code: str, message: str) -> None:
        """Initialise a structured read-only light-state failure."""
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class LightStateQueryRequest:
    """Parsed deterministic Home Assistant light-state query."""

    intent: str
    target: str
    scope: str = "entity"
    requested_domain: str | None = None
    requested_label: str | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serialisable payload for the service layer."""
        return {
            "intent": self.intent,
            "target": self.target,
            "scope": self.scope,
            "requested_domain": self.requested_domain,
            "requested_label": self.requested_label,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "LightStateQueryRequest":
        """Build a request from a service payload."""
        return cls(
            intent=str(payload.get("intent") or "").strip(),
            target=str(payload.get("target") or "").strip(),
            scope=str(payload.get("scope") or "entity").strip() or "entity",
            requested_domain=(
                str(payload.get("requested_domain") or "").strip() or None
            ),
            requested_label=(
                str(payload.get("requested_label") or "").strip() or None
            ),
        )


@dataclass(frozen=True)
class LightStateQueryResult:
    """Rendered light-state query result and supporting provenance fields."""

    content: str
    entity_ids: tuple[str, ...]
    areas: tuple[str, ...]
    status: str = "complete"


_AREA_NOUNS = {"light", "lights", "lamp", "lamps"}
_STATE_VALUES = {"on", "off", "unavailable", "unknown"}
_COLOR_TEMP_LABELS = (
    ("warm white", 2700, 2850),
    ("soft white", 3000, 3500),
    ("neutral white", 4000, 4500),
    ("cool white", 5000, 5750),
    ("daylight", 6500, 7000),
)


def parse_light_state_query(prompt: str) -> LightStateQueryRequest | None:
    """Parse a deterministic live light-state query."""
    command = _normalise(prompt)
    area_patterns = (
        (r"^(?:please )?are any (?:the )?(.+?) (?:lights?|lamps?) on$", "area_any_on"),
        (r"^(?:please )?which (?:the )?(.+?) (?:lights?|lamps?) are on$", "area_list_on"),
        (r"^(?:please )?are all (?:the )?(.+?) (?:lights?|lamps?) off$", "area_all_off"),
    )
    for pattern, intent in area_patterns:
        match = re.fullmatch(pattern, command)
        if match is None:
            continue
        return LightStateQueryRequest(
            intent=intent,
            target=_strip_target(match.group(1)),
            scope="area",
            requested_domain="light",
        )

    patterns = (
        (r"^(?:please )?(?:is|are) (?:the )?(.+?) (on|off)$", "state"),
        (r"^(?:please )?what state is (?:the )?(.+?) in$", "state"),
        (r"^(?:please )?how bright is (?:the )?(.+?)$", "brightness"),
        (r"^(?:please )?what brightness is (?:the )?(.+?) set to$", "brightness"),
        (r"^(?:please )?what brightness is (?:the )?(.+?)$", "brightness"),
        (
            r"^(?:please )?what brightness and colour is (?:the )?(.+?)$",
            "setting",
        ),
        (
            r"^(?:please )?what brightness and color is (?:the )?(.+?)$",
            "setting",
        ),
        (r"^(?:please )?what setting is (?:the )?(.+?) on$", "setting"),
        (r"^(?:please )?what setting is (?:the )?(.+?) in$", "setting"),
        (r"^(?:please )?what colour temperature is (?:the )?(.+?)$", "color_temperature"),
        (r"^(?:please )?what color temperature is (?:the )?(.+?)$", "color_temperature"),
        (r"^(?:please )?what colour is (?:the )?(.+?)$", "color"),
        (r"^(?:please )?what color is (?:the )?(.+?)$", "color"),
        (
            r"^(?:please )?is (?:the )?(.+?) "
            r"(warm white|soft white|neutral white|cool white|daylight)$",
            "color_temperature",
        ),
    )
    for pattern, intent in patterns:
        match = re.fullmatch(pattern, command)
        if match is None:
            continue
        target = _strip_target(match.group(1))
        requested_label = None
        if intent == "color_temperature" and len(match.groups()) > 1:
            requested_label = _normalise(match.group(2))
        requested_domain = _requested_domain(target)
        if requested_domain is None and "lamp" in target:
            requested_domain = "light"
        return LightStateQueryRequest(
            intent=intent if requested_label is None else "color_temperature_check",
            target=target,
            requested_domain=requested_domain,
            requested_label=requested_label,
        )

    return None


def render_light_state_query(
    request: LightStateQueryRequest,
    live_states: list[Mapping[str, Any]],
) -> LightStateQueryResult:
    """Render one light-state query from live Home Assistant states."""
    ordered_states = [state for state in live_states if _entity_id(state)]
    if request.scope == "area":
        return _render_area_query(request, ordered_states)

    if not ordered_states:
        raise LightStateQueryError(
            "unknown_target",
            f"Home Assistant target '{request.target}' was not found.",
        )
    if len(ordered_states) > 1:
        raise LightStateQueryError(
            "ambiguous_target",
            f"Home Assistant target '{request.target}' is ambiguous.",
        )

    state = ordered_states[0]
    content = _render_entity_query(request, state)
    entity_id = str(state.get("entity_id") or "").strip().lower()
    return LightStateQueryResult(
        content=content,
        entity_ids=(entity_id,),
        areas=(),
    )


def _render_entity_query(request: LightStateQueryRequest, state: Mapping[str, Any]) -> str:
    """Render one entity-level read-back answer."""
    name = light_target_display_name(state, request.target)
    state_text = _state_text(state)
    if request.intent == "state":
        return f"The {name} is {state_text}."

    if _is_switch_entity(state) and request.intent in {"brightness", "color", "setting", "color_temperature", "color_temperature_check"}:
        return (
            f"The {name} is a switch, so I can report whether it is on or off, "
            "but not brightness or colour."
        )

    brightness_pct = _brightness_pct(state)
    kelvin = _color_temp_kelvin(state)
    color_desc = _color_description(state)

    if request.intent == "brightness":
        return _render_brightness(name, state_text, brightness_pct)
    if request.intent == "color_temperature":
        return _render_color_temperature(name, state_text, kelvin)
    if request.intent == "color_temperature_check":
        return _render_color_temperature_check(
            name,
            state_text,
            kelvin,
            request.requested_label,
        )
    if request.intent == "color":
        return _render_color(name, state_text, color_desc)
    if request.intent == "setting":
        parts: list[str] = []
        if brightness_pct is not None:
            parts.append(f"at {brightness_pct} percent brightness")
        if kelvin is not None:
            parts.append(_temperature_phrase(kelvin))
        elif color_desc is not None:
            parts.append(color_desc)
        if not parts:
            return f"Home Assistant is not exposing a current setting for the {name}."
        if state_text == "off":
            return f"The {name} is off. Its last-known setting is {' and '.join(parts)}."
        return f"The {name} is on {' and '.join(parts)}."

    return f"Home Assistant could not complete the light-state query for the {name}."


def _render_brightness(name: str, state_text: str, brightness_pct: int | None) -> str:
    if brightness_pct is None:
        return f"Home Assistant is not exposing brightness for the {name}."
    if state_text == "off":
        return f"The {name} is off. Its last-known brightness setting is {brightness_pct} percent."
    return f"The {name} is on at {brightness_pct} percent brightness."


def _render_color_temperature(name: str, state_text: str, kelvin: int | None) -> str:
    if kelvin is None:
        return f"Home Assistant is not exposing a current colour temperature for the {name}."
    phrase = _temperature_phrase(kelvin)
    if state_text == "off":
        return f"The {name} is off. Its last-known setting is {phrase}."
    return f"The {name} is on and set to {phrase}."


def _render_color_temperature_check(
    name: str,
    state_text: str,
    kelvin: int | None,
    requested_label: str | None,
) -> str:
    if kelvin is None:
        return f"Home Assistant is not exposing a current colour temperature for the {name}."
    phrase = _temperature_phrase(kelvin)
    if requested_label is None:
        return _render_color_temperature(name, state_text, kelvin)
    if state_text == "off":
        if phrase.startswith(requested_label):
            return f"The {name} is off. Its last-known setting is {requested_label}, around {kelvin} Kelvin."
        return f"The {name} is off. Its last-known setting is {phrase}."
    if phrase.startswith(requested_label):
        return f"The {name} is {requested_label}, around {kelvin} Kelvin."
    return f"The {name} is not {requested_label}; it is {phrase}."


def _render_color(name: str, state_text: str, color_desc: str | None) -> str:
    if color_desc is None:
        return f"Home Assistant is not exposing a current colour setting for the {name}."
    if state_text == "off":
        return f"The {name} is off. Its last-known setting is {color_desc}."
    return f"The {name} is on, {color_desc}."


def _render_area_query(
    request: LightStateQueryRequest,
    states: list[Mapping[str, Any]],
) -> LightStateQueryResult:
    """Render one area-level summary query."""
    area_name = _humanize_phrase(request.target)
    if not states:
        raise LightStateQueryError(
            "unknown_target",
            f"Home Assistant target '{request.target}' was not found.",
        )

    rendered = [
        (light_target_display_name(state, _entity_object_id(state)), _state_text(state))
        for state in states
    ]
    on_names = [name for name, state_text in rendered if state_text == "on"]
    off_names = [name for name, state_text in rendered if state_text == "off"]
    unavailable_names = [name for name, state_text in rendered if state_text == "unavailable"]
    unknown_names = [name for name, state_text in rendered if state_text == "unknown"]

    if request.intent == "area_list_on":
        if not on_names:
            content = f"No {area_name} lights are on."
        else:
            content = f"{len(on_names)} {area_name} lights are on: {_join_names(on_names)}."
        return LightStateQueryResult(
            content=_append_area_state_details(content, off_names, unavailable_names, unknown_names),
            entity_ids=tuple(_entity_id(state) for state in states),
            areas=(request.target,),
        )

    if request.intent == "area_any_on":
        if on_names:
            content = f"{len(on_names)} {area_name} lights are on: {_join_names(on_names)}."
        else:
            content = f"No {area_name} lights are on."
        return LightStateQueryResult(
            content=_append_area_state_details(content, off_names, unavailable_names, unknown_names),
            entity_ids=tuple(_entity_id(state) for state in states),
            areas=(request.target,),
        )

    if request.intent == "area_all_off":
        if on_names:
            content = f"No, {len(on_names)} {area_name} lights are on: {_join_names(on_names)}."
        else:
            content = f"All {area_name} lights are off."
        return LightStateQueryResult(
            content=_append_area_state_details(content, off_names, unavailable_names, unknown_names),
            entity_ids=tuple(_entity_id(state) for state in states),
            areas=(request.target,),
        )

    raise LightStateQueryError(
        "unsupported_query",
        "That Home Assistant light-state query is not supported.",
    )


def _append_area_state_details(
    content: str,
    off_names: list[str],
    unavailable_names: list[str],
    unknown_names: list[str],
) -> str:
    """Append concise details for non-on states in an area summary."""
    extra: list[str] = []
    if off_names:
        extra.append(f"{len(off_names)} off: {_join_names(off_names)}")
    if unavailable_names:
        extra.append(f"{len(unavailable_names)} unavailable: {_join_names(unavailable_names)}")
    if unknown_names:
        extra.append(f"{len(unknown_names)} unknown: {_join_names(unknown_names)}")
    if not extra:
        return content
    return f"{content} {' '.join(extra)}."


def _state_text(state: Mapping[str, Any]) -> str:
    """Return a normalised live state text."""
    value = _normalise(state.get("state"))
    if value in _STATE_VALUES:
        return value
    return value or "unknown"


def _brightness_pct(state: Mapping[str, Any]) -> int | None:
    """Return live brightness as a percentage."""
    brightness = _attributes(state).get("brightness")
    try:
        if brightness is None:
            return None
        return max(1, min(100, round((int(brightness) / 255) * 100)))
    except (TypeError, ValueError):
        return None


def _color_temp_kelvin(state: Mapping[str, Any]) -> int | None:
    """Return live colour temperature in Kelvin."""
    kelvin = _attributes(state).get("color_temp_kelvin")
    try:
        return int(kelvin) if kelvin is not None else None
    except (TypeError, ValueError):
        return None


def _color_description(state: Mapping[str, Any]) -> str | None:
    """Return a safe human description of the live colour state."""
    attributes = _attributes(state)
    color_mode = _normalise(attributes.get("color_mode"))
    if color_mode == "color_temp":
        kelvin = _color_temp_kelvin(state)
        if kelvin is not None:
            return _temperature_phrase(kelvin)
        return None

    rgb = attributes.get("rgb_color")
    hs = attributes.get("hs_color")
    xy = attributes.get("xy_color")
    if isinstance(rgb, (list, tuple)) and len(rgb) >= 3:
        try:
            rgb_value = tuple(int(value) for value in rgb[:3])
        except (TypeError, ValueError):
            rgb_value = None
        else:
            label = describe_rgb_color(rgb_value)
            if label is not None:
                return f"roughly a {label} colour, with RGB values {rgb_value[0]}, {rgb_value[1]}, {rgb_value[2]}"
            return f"RGB colour {rgb_value[0]}, {rgb_value[1]}, {rgb_value[2]}"
    if isinstance(hs, (list, tuple)) and len(hs) >= 2:
        try:
            hue = float(hs[0])
            saturation = float(hs[1])
        except (TypeError, ValueError):
            pass
        else:
            label = _hs_label(hue, saturation)
            if label is not None:
                return f"colour {label}"
            return f"HS colour {hue:.1f}, {saturation:.1f}"
    if isinstance(xy, (list, tuple)) and len(xy) >= 2:
        try:
            x_val = float(xy[0])
            y_val = float(xy[1])
        except (TypeError, ValueError):
            return None
        return f"XY colour {x_val:.3f}, {y_val:.3f}"
    return None


def _hs_label(hue: float, saturation: float) -> str | None:
    """Map a small set of safe HS values to common colour labels."""
    if saturation < 10:
        return "white"
    if 180 <= hue < 260:
        return "blue"
    if 260 <= hue < 320:
        return "purple"
    if 320 <= hue or hue < 20:
        return "red"
    if 20 <= hue < 55:
        return "orange"
    if 55 <= hue < 95:
        return "yellow"
    if 95 <= hue < 170:
        return "green"
    if 170 <= hue < 180:
        return "cyan"
    return None


def _temperature_phrase(kelvin: int) -> str:
    """Return a human phrase for a Kelvin value."""
    label = _temperature_label(kelvin)
    return f"{label}, around {kelvin} Kelvin"


def _temperature_label(kelvin: int) -> str:
    """Return an approximate temperature label for a Kelvin value."""
    for label, lower, upper in _COLOR_TEMP_LABELS:
        if lower <= kelvin <= upper:
            return label
    return "white"


def _temperature_label_from_target(target: str) -> str | None:
    """Return the requested temperature label from a query target."""
    for label, _, _ in _COLOR_TEMP_LABELS:
        if label in _normalise(target):
            return label
    return None


def _entity_id(state: Mapping[str, Any]) -> str:
    """Return the live entity ID for a state row."""
    return str(state.get("entity_id") or "").strip().lower()


def _entity_object_id(state: Mapping[str, Any]) -> str:
    """Return a readable fallback name from a live state row."""
    entity_id = _entity_id(state)
    object_id = entity_id.partition(".")[2].replace("_", " ")
    return object_id or entity_id


def _attributes(state: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return the state attribute mapping if present."""
    attributes = state.get("attributes")
    return attributes if isinstance(attributes, Mapping) else {}


def _is_switch_entity(state: Mapping[str, Any]) -> bool:
    """Return whether a live state row belongs to a switch entity."""
    return _entity_id(state).startswith("switch.")


def _join_names(names: list[str]) -> str:
    """Join names for human-readable summaries."""
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def _humanize_phrase(value: str) -> str:
    """Return a title-cased human area label."""
    words = _normalise(value).split()
    if not words:
        return ""
    return " ".join(word.capitalize() for word in words)


def _normalise(value: Any) -> str:
    """Return canonical lowercase text for deterministic comparisons."""
    text = re.sub(r"[^a-z0-9_.\s-]", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _strip_target(value: Any) -> str:
    """Return a normalised spoken target phrase without trailing punctuation."""
    return _normalise(value).strip(".- ")


def _requested_domain(target: str) -> str | None:
    """Infer a requested domain from explicit target wording."""
    words = _normalise(target).split()
    if not words:
        return None
    if words[-1] in {"switch", "switches"}:
        return "switch"
    if words[-1] in _AREA_NOUNS:
        return "light"
    return "light" if any(word in {"light", "lights", "lamp", "lamps"} for word in words) else None
