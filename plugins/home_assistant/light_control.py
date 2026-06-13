"""Deterministic Home Assistant light-control parsing and planning."""
# Author: Clive Bostock
# Date: 12-Jun-2026
# Description: Parses richer light commands and validates live capabilities.

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .control import HomeAssistantControlError


RELATIVE_BRIGHTNESS_STEP_PERCENT = 10
RELATIVE_COLOR_TEMP_STEP_KELVIN = 300

COLOR_NAME_ALLOWLIST = frozenset(
    {
        "blue",
        "cyan",
        "green",
        "magenta",
        "orange",
        "pink",
        "purple",
        "red",
        "teal",
        "yellow",
    }
)

COLOR_TEMP_PRESETS = {
    "warm white": 2700,
    "soft white": 3000,
    "normal white": 4000,
    "neutral white": 4000,
    "cool white": 5000,
    "daylight": 6500,
    "toasty": 2700,
}

_COLOR_TEMP_LABELS = {
    2700: "warm white",
    3000: "soft white",
    4000: "normal white",
    5000: "cool white",
    6500: "daylight",
}

_BRIGHTNESS_CAPABLE_MODES = {
    "brightness",
    "color_temp",
    "hs",
    "rgb",
    "rgbw",
    "rgbww",
    "xy",
}
_COLOR_CAPABLE_MODES = {
    "hs",
    "rgb",
    "rgbw",
    "rgbww",
    "xy",
}
_COLOR_TEMP_CAPABLE_MODES = {"color_temp"}
_ACRONYMS = {"tv", "rgb", "hd", "led", "usb"}


class LightControlError(HomeAssistantControlError):
    """Raised when a light-control request cannot be completed safely."""


@dataclass(frozen=True)
class LightControlRequest:
    """Parsed deterministic Home Assistant light-control request."""

    target: str
    kind: str
    value: int | str
    label: str | None = None
    turn_on: bool = True

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-serialisable payload for the service layer."""
        return {
            "target": self.target,
            "kind": self.kind,
            "value": self.value,
            "label": self.label,
            "turn_on": self.turn_on,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "LightControlRequest":
        """Build a request from a service payload."""
        return cls(
            target=str(payload.get("target") or "").strip(),
            kind=str(payload.get("kind") or "").strip(),
            value=payload.get("value"),
            label=(
                str(payload.get("label") or "").strip() or None
                if payload.get("label") is not None
                else None
            ),
            turn_on=bool(payload.get("turn_on", True)),
        )


@dataclass(frozen=True)
class LightCapabilities:
    """Light capability snapshot derived from one live Home Assistant state."""

    supported_color_modes: frozenset[str]
    brightness: int | None
    color_mode: str | None
    color_temp_kelvin: int | None
    min_color_temp_kelvin: int | None
    max_color_temp_kelvin: int | None
    hs_color: tuple[float, float] | None
    rgb_color: tuple[int, int, int] | None
    xy_color: tuple[float, float] | None
    effect_list: frozenset[str]

    @property
    def can_adjust_brightness(self) -> bool:
        """Return whether the light supports brightness changes."""
        if self.brightness is not None:
            return True
        if self.supported_color_modes & _BRIGHTNESS_CAPABLE_MODES:
            return True
        return self.color_mode in _BRIGHTNESS_CAPABLE_MODES

    @property
    def can_set_color(self) -> bool:
        """Return whether the light supports colour selection."""
        if self.supported_color_modes & _COLOR_CAPABLE_MODES:
            return True
        return any(item is not None for item in (self.hs_color, self.rgb_color, self.xy_color))

    @property
    def can_set_color_temp(self) -> bool:
        """Return whether the light supports colour-temperature control."""
        if self.supported_color_modes & _COLOR_TEMP_CAPABLE_MODES:
            return True
        return any(
            value is not None
            for value in (
                self.color_temp_kelvin,
                self.min_color_temp_kelvin,
                self.max_color_temp_kelvin,
            )
        ) or self.color_mode == "color_temp"


def parse_light_control_command(prompt: str) -> LightControlRequest | None:
    """Parse a deterministic rich Home Assistant light-control command."""
    command = _strip_target(prompt)
    patterns: list[tuple[str, str]] = [
        (r"^(?:please )?dim (?:the )?(.+)$", "dim"),
        (r"^(?:please )?brighten (?:the )?(.+)$", "brighten"),
        (r"^(?:please )?make (?:the )?(.+?) a bit brighter$", "brighten"),
        (r"^(?:please )?make (?:the )?(.+?) a bit dimmer$", "dim"),
        (r"^(?:please )?make (?:the )?(.+?) warmer$", "warmer"),
        (r"^(?:please )?make (?:the )?(.+?) cooler$", "cooler"),
        (r"^(?:please )?turn on (?:the )?(.+?) at (\d{1,3}) percent$", "brightness_pct"),
        (
            r"^(?:please )?turn on (?:the )?(.+?) brightness to (\d{1,3}) percent$",
            "brightness_pct",
        ),
        (
            r"^(?:please )?set (?:the )?(.+?) brightness to (\d{1,3}) percent$",
            "brightness_pct",
        ),
        (r"^(?:please )?set (?:the )?(.+?) to (\d{1,3}) percent$", "brightness_pct"),
        (
            r"^(?:please )?turn on (?:the )?(.+?) to (\d{1,3}) percent$",
            "brightness_pct",
        ),
        (
            r"^(?:please )?reset (?:the )?(.+?) to "
            r"(normal white|neutral white|warm white|soft white|cool white|daylight|toasty)$",
            "color_temp_preset",
        ),
        (
            r"^(?:please )?(?:set|make|turn on) (?:the )?(.+?) to (\d{3,4}) kelvin$",
            "color_temp_kelvin",
        ),
        (
            r"^(?:please )?(?:set|make|turn on) (?:the )?(.+?) to "
            r"(normal white|neutral white|warm white|soft white|cool white|daylight|toasty)$",
            "color_temp_preset",
        ),
        (
            r"^(?:please )?(?:set|make|turn on) (?:the )?(.+?) "
            r"(normal white|neutral white|warm white|soft white|cool white|daylight|toasty)$",
            "color_temp_preset",
        ),
        (
            r"^(?:please )?(?:set|make|turn on) (?:the )?(.+?) to "
            r"(blue|cyan|green|magenta|orange|pink|purple|red|teal|yellow)$",
            "color_name",
        ),
        (r"^(?:please )?(?:make|set|turn on) (?:the )?(.+?) (blue|cyan|green|magenta|orange|pink|purple|red|teal|yellow)$", "color_name"),
    ]
    for pattern, kind in patterns:
        match = re.fullmatch(pattern, command)
        if match is None:
            continue
        target = _strip_target(match.group(1))
        if kind == "brightness_pct":
            value = int(match.group(2))
            return LightControlRequest(target=target, kind=kind, value=value)
        if kind == "dim":
            return LightControlRequest(
                target=target,
                kind="brightness_step",
                value=-RELATIVE_BRIGHTNESS_STEP_PERCENT,
            )
        if kind == "brighten":
            return LightControlRequest(
                target=target,
                kind="brightness_step",
                value=RELATIVE_BRIGHTNESS_STEP_PERCENT,
            )
        if kind == "warmer":
            return LightControlRequest(
                target=target,
                kind="color_temp_step",
                value=-RELATIVE_COLOR_TEMP_STEP_KELVIN,
            )
        if kind == "cooler":
            return LightControlRequest(
                target=target,
                kind="color_temp_step",
                value=RELATIVE_COLOR_TEMP_STEP_KELVIN,
            )
        if kind == "color_temp_kelvin":
            return LightControlRequest(
                target=target,
                kind=kind,
                value=int(match.group(2)),
            )
        if kind == "color_temp_preset":
            label = _normalise_preset_label(match.group(2))
            return LightControlRequest(
                target=target,
                kind="color_temp_kelvin",
                value=COLOR_TEMP_PRESETS[label],
                label=label,
            )
        if kind == "color_name":
            color_name = _normalise(match.group(2))
            return LightControlRequest(
                target=target,
                kind=kind,
                value=color_name,
                label=color_name,
            )
    return None


def extract_light_capabilities(state: Mapping[str, Any]) -> LightCapabilities:
    """Return a live capability snapshot from one Home Assistant light state."""
    attributes = _attributes(state)
    supported_color_modes = _json_text_set(attributes.get("supported_color_modes"))
    return LightCapabilities(
        supported_color_modes=supported_color_modes,
        brightness=_int_or_none(attributes.get("brightness")),
        color_mode=_normalise(attributes.get("color_mode")) or None,
        color_temp_kelvin=_int_or_none(attributes.get("color_temp_kelvin")),
        min_color_temp_kelvin=_int_or_none(attributes.get("min_color_temp_kelvin")),
        max_color_temp_kelvin=_int_or_none(attributes.get("max_color_temp_kelvin")),
        hs_color=_tuple_float_two(attributes.get("hs_color")),
        rgb_color=_tuple_int_three(attributes.get("rgb_color")),
        xy_color=_tuple_float_two(attributes.get("xy_color")),
        effect_list=_json_text_set(attributes.get("effect_list")),
    )


def build_light_service_data(
    request: LightControlRequest,
    state: Mapping[str, Any],
    *,
    target_label: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Validate one live light state and return the Home Assistant service data."""
    capabilities = extract_light_capabilities(state)
    display_name = target_label or light_target_display_name(state, request.target)

    if request.kind == "brightness_pct":
        brightness_pct = _validate_brightness_pct(request.value)
        if not capabilities.can_adjust_brightness:
            raise LightControlError(
                "unsupported_brightness",
                "That light does not appear to support brightness control.",
            )
        return {"brightness_pct": brightness_pct}, _brightness_response(
            brightness_pct,
            display_name,
        )

    if request.kind == "brightness_step":
        if not capabilities.can_adjust_brightness:
            raise LightControlError(
                "unsupported_brightness",
                "That light does not appear to support brightness control.",
            )
        current_pct = _current_brightness_pct(capabilities)
        if current_pct is None:
            raise LightControlError(
                "missing_brightness",
                "I cannot read the current brightness from Home Assistant, so I cannot dim or brighten that light.",
            )
        target_pct = _clamp_percent(current_pct + int(request.value))
        return {"brightness_pct": target_pct}, _step_brightness_response(
            target_pct,
            int(request.value),
            display_name,
        )

    if request.kind == "color_name":
        color_name = _normalise(request.value)
        if color_name not in COLOR_NAME_ALLOWLIST:
            raise LightControlError(
                "unsupported_color_name",
                f"I do not recognise the colour '{request.value}'.",
            )
        if not capabilities.can_set_color:
            raise LightControlError(
                "unsupported_colour",
                "That light does not appear to support colour control.",
            )
        return {"color_name": color_name}, _colour_response(color_name, display_name)

    if request.kind == "color_temp_kelvin":
        if not capabilities.can_set_color_temp:
            raise LightControlError(
                "unsupported_color_temp",
                "That light does not appear to support colour temperature.",
            )
        kelvin = _validate_color_temp_kelvin(request.value)
        kelvin = _clamp_kelvin(
            kelvin,
            capabilities.min_color_temp_kelvin,
            capabilities.max_color_temp_kelvin,
        )
        return {"color_temp_kelvin": kelvin}, _colour_temperature_response(
            kelvin,
            display_name,
            request.label,
        )

    if request.kind == "color_temp_step":
        if not capabilities.can_set_color_temp:
            raise LightControlError(
                "unsupported_color_temp",
                "That light does not appear to support colour temperature.",
            )
        current_kelvin = _current_color_temp_kelvin(capabilities)
        if current_kelvin is None:
            raise LightControlError(
                "missing_color_temp",
                "I cannot read the current colour temperature from Home Assistant, so I cannot adjust it.",
            )
        kelvin = _clamp_kelvin(
            current_kelvin + int(request.value),
            capabilities.min_color_temp_kelvin,
            capabilities.max_color_temp_kelvin,
        )
        return {"color_temp_kelvin": kelvin}, _colour_temperature_response(
            kelvin,
            display_name,
            request.label,
        )

    raise LightControlError(
        "unsupported_light_command",
        "That light request is not supported.",
    )


def light_target_display_name(state: Mapping[str, Any], fallback: str) -> str:
    """Return a concise display name for a light target."""
    attributes = _attributes(state)
    name = (
        attributes.get("friendly_name")
        or attributes.get("name")
        or fallback
    )
    text = str(name)
    if attributes.get("friendly_name") or attributes.get("name"):
        return text
    return _humanize_phrase(text)


def _brightness_response(
    brightness_pct: int,
    target: str | None,
) -> str:
    target = target or "Light"
    return f"{target} set to {brightness_pct} percent."


def _step_brightness_response(
    brightness_pct: int,
    step: int,
    target: str | None,
) -> str:
    target = target or "Light"
    verb = "brightened" if step > 0 else "dimmed"
    return f"{target} {verb} to {brightness_pct} percent."


def _colour_response(color_name: str, target: str | None) -> str:
    target = target or "Light"
    return f"{target} set to {color_name}."


def _colour_temperature_response(
    kelvin: int,
    target: str | None,
    value_label: str | None,
) -> str:
    target = target or "Light"
    temperature_label = _COLOR_TEMP_LABELS.get(kelvin)
    value = temperature_label or f"{kelvin} K"
    if temperature_label is None and value_label is not None and value_label in COLOR_TEMP_PRESETS:
        value = value_label
    return f"{target} set to {value}."


def _current_brightness_pct(capabilities: LightCapabilities) -> int | None:
    if capabilities.brightness is None:
        return None
    return max(1, min(100, round((capabilities.brightness / 255) * 100)))


def _current_color_temp_kelvin(capabilities: LightCapabilities) -> int | None:
    if capabilities.color_temp_kelvin is not None:
        return capabilities.color_temp_kelvin
    return None


def _validate_brightness_pct(value: Any) -> int:
    brightness_pct = _int_or_none(value)
    if brightness_pct is None or not 1 <= brightness_pct <= 100:
        raise LightControlError(
            "invalid_brightness",
            "Brightness must be between 1 and 100 percent.",
        )
    return brightness_pct


def _validate_color_temp_kelvin(value: Any) -> int:
    kelvin = _int_or_none(value)
    if kelvin is None or kelvin < 1000 or kelvin > 10000:
        raise LightControlError(
            "invalid_color_temp",
            "Colour temperature must be a Kelvin value.",
        )
    return kelvin


def _clamp_percent(value: int) -> int:
    return max(1, min(100, value))


def _clamp_kelvin(
    value: int,
    min_kelvin: int | None,
    max_kelvin: int | None,
) -> int:
    lower = min_kelvin if min_kelvin is not None else value
    upper = max_kelvin if max_kelvin is not None else value
    if lower > upper:
        lower, upper = upper, lower
    return max(lower, min(upper, value))


def _normalise(value: Any) -> str:
    text = re.sub(r"[^a-z0-9_.\s-]", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _strip_target(value: Any) -> str:
    return _normalise(value).strip(".- ")


def _humanize_phrase(value: str) -> str:
    words = _normalise(value).split()
    if not words:
        return ""
    result = []
    for index, word in enumerate(words):
        if word in _ACRONYMS:
            result.append(word.upper())
        elif index == 0:
            result.append(word.capitalize())
        else:
            result.append(word)
    return " ".join(result)


def _normalise_preset_label(value: Any) -> str:
    return _normalise(value)


def _attributes(state: Mapping[str, Any]) -> Mapping[str, Any]:
    attributes = state.get("attributes")
    return attributes if isinstance(attributes, Mapping) else {}


def _json_text_set(value: Any) -> frozenset[str]:
    if value is None:
        return frozenset()
    if isinstance(value, str):
        return frozenset({_normalise(value)}) if _normalise(value) else frozenset()
    if not isinstance(value, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset({_normalise(item) for item in value if _normalise(item)})


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _tuple_float_two(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None


def _tuple_int_three(value: Any) -> tuple[int, int, int] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 3:
        return None
    try:
        return int(value[0]), int(value[1]), int(value[2])
    except (TypeError, ValueError):
        return None
