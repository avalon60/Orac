"""Deterministic Home Assistant device-control parsing and resolution."""
# Author: Clive Bostock
# Date: 11-Jun-2026
# Description: Validates low-risk commands and resolves synced Home Assistant targets.

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any, Iterable, Mapping


ALLOWED_SERVICES = {
    "light": {
        "turn_on": "turn_on",
        "turn_off": "turn_off",
        "toggle": "toggle",
    },
    "switch": {
        "turn_on": "turn_on",
        "turn_off": "turn_off",
        "toggle": "toggle",
    },
    "scene": {
        "activate": "turn_on",
    },
}

BLOCKED_DOMAINS = frozenset(
    {
        "alarm_control_panel",
        "automation",
        "button",
        "climate",
        "cover",
        "fan",
        "input_boolean",
        "lock",
        "remote",
        "script",
        "siren",
        "valve",
    }
)

_DOMAIN_TERMS = {
    "light": "light",
    "lights": "light",
    "lamp": "light",
    "lamps": "light",
    "switch": "switch",
    "switches": "switch",
    "scene": "scene",
    "scenes": "scene",
    "lock": "lock",
    "locks": "lock",
    "door": "cover",
    "doors": "cover",
    "blind": "cover",
    "blinds": "cover",
    "shutter": "cover",
    "shutters": "cover",
    "thermostat": "climate",
    "thermostats": "climate",
    "fan": "fan",
    "fans": "fan",
}

_WHOLE_HOME_TARGETS = frozenset(
    {
        "all",
        "all devices",
        "all lights",
        "all lamps",
        "all switches",
        "entire home",
        "entire house",
        "every device",
        "every light",
        "every lamp",
        "every switch",
        "everything",
        "whole home",
        "whole house",
    }
)


class HomeAssistantControlError(ValueError):
    """Raised when a control command or target must be refused."""

    def __init__(self, code: str, message: str) -> None:
        """Initialise a structured control refusal."""
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ControlRequest:
    """Parsed low-risk Home Assistant control request."""

    action: str
    target: str
    requested_domain: str | None = None


@dataclass(frozen=True)
class ControlServiceCall:
    """One allowlisted Home Assistant service call."""

    domain: str
    service: str
    entity_ids: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedControl:
    """Validated Home Assistant service calls and resolved entities."""

    action: str
    service_calls: tuple[ControlServiceCall, ...]
    target: str
    resolution: str

    @property
    def entity_ids(self) -> tuple[str, ...]:
        """Return all resolved entity IDs in deterministic order."""
        return tuple(
            sorted(
                entity_id
                for service_call in self.service_calls
                for entity_id in service_call.entity_ids
            )
        )


def parse_control_command(prompt: str) -> ControlRequest | None:
    """Parse a supported device-control phrase without fuzzy interpretation.

    Args:
        prompt: User command text.

    Returns:
        A parsed request, or ``None`` when the phrase is not a control command.

    Raises:
        HomeAssistantControlError: If the command addresses the whole home.
    """
    command = _normalise_target(prompt)
    patterns = (
        (r"^(?:please )?(?:turn|switch) (on|off) (?:the )?(.+)$", None),
        (r"^(?:please )?(?:turn|switch) (?:the )?(.+?) (on|off)$", "trailing"),
        (r"^(?:please )?(on|off) (?:the )?(.+)$", None),
        (r"^(?:please )?toggle (?:the )?(.+)$", "toggle"),
        (r"^(?:please )?(?:activate|enable) (?:the )?(.+)$", "activate"),
    )
    for pattern, fixed_action in patterns:
        match = re.fullmatch(pattern, command)
        if match is None:
            continue
        if fixed_action == "trailing":
            action = "turn_on" if match.group(2) == "on" else "turn_off"
            target = match.group(1)
        elif fixed_action is None:
            action = "turn_on" if match.group(1) == "on" else "turn_off"
            target = match.group(2)
        else:
            action = fixed_action
            target = match.group(1)
        target = _normalise_target(target)
        if target in _WHOLE_HOME_TARGETS:
            raise HomeAssistantControlError(
                "whole_home_refused",
                "Whole-home Home Assistant commands are not allowed.",
            )
        requested_domain = _requested_domain(target, action)
        if requested_domain == "scene" and action == "turn_on":
            action = "activate"
        if requested_domain == "scene" and target.startswith("scene "):
            target = target.removeprefix("scene ").strip()
        return ControlRequest(
            action=action,
            target=target,
            requested_domain=requested_domain,
        )
    return None


def resolve_control_target(
    request: ControlRequest,
    rows: Iterable[Mapping[str, Any]],
) -> ResolvedControl:
    """Resolve a control request using aliases, exact names, then areas.

    Args:
        request: Parsed control request.
        rows: Rows from ``orac_ha.ha_control_resolution_v``.

    Returns:
        A validated service call with one or more entity IDs.

    Raises:
        HomeAssistantControlError: If the domain, action, or target is unsafe or
            cannot be resolved deterministically.
    """
    if request.requested_domain in BLOCKED_DOMAINS:
        raise HomeAssistantControlError(
            "blocked_domain",
            f"Home Assistant domain '{request.requested_domain}' is not allowed.",
        )

    entities = _normalise_rows(rows)
    alias_matches = [
        row for row in entities if row["alias_name"] == _normalise(request.target)
    ]
    if alias_matches:
        return _build_resolution(request, alias_matches, "alias")

    exact_matches = [row for row in entities if _matches_exact_name(row, request)]
    exact_matches = _deduplicate_entities(exact_matches)
    eligible_exact_matches = [
        row for row in exact_matches if _domain_matches(row, request.requested_domain)
    ]
    if len(eligible_exact_matches) > 1:
        raise HomeAssistantControlError(
            "ambiguous_target",
            f"Home Assistant target '{request.target}' is ambiguous.",
        )
    if eligible_exact_matches:
        return _build_resolution(request, eligible_exact_matches, "entity")
    if exact_matches:
        return _build_resolution(request, exact_matches, "entity")

    area_matches = [row for row in entities if _matches_area(row, request)]
    area_matches = _deduplicate_entities(area_matches)
    if area_matches:
        return _build_resolution(request, area_matches, "area")

    raise HomeAssistantControlError(
        "unknown_target",
        f"Home Assistant target '{request.target}' was not found.",
    )


def _build_resolution(
    request: ControlRequest,
    rows: list[dict[str, Any]],
    resolution: str,
) -> ResolvedControl:
    """Validate matched rows and build allowlisted service calls."""
    blocked = sorted({row["domain"] for row in rows} & BLOCKED_DOMAINS)
    if blocked:
        raise HomeAssistantControlError(
            "blocked_domain",
            f"Home Assistant domain '{blocked[0]}' is not allowed.",
        )
    if resolution == "alias" and any(
        not _domain_matches(row, request.requested_domain) for row in rows
    ):
        raise HomeAssistantControlError(
            "unsupported_combination",
            "The Home Assistant alias contains incompatible entity types.",
        )
    eligible = [row for row in rows if _domain_matches(row, request.requested_domain)]
    if not eligible:
        raise HomeAssistantControlError(
            "unsupported_combination",
            "That action is not supported for the requested Home Assistant target.",
        )

    calls_by_service: dict[tuple[str, str], set[str]] = {}
    for row in eligible:
        service = _service_for(row["domain"], request.action)
        if service is None:
            raise HomeAssistantControlError(
                "unsupported_combination",
                "That action is not supported for the requested Home Assistant target.",
            )
        calls_by_service.setdefault((row["domain"], service), set()).add(
            row["entity_id"]
        )
    if not calls_by_service:
        raise HomeAssistantControlError(
            "unsupported_combination",
            "That action is not supported for the requested Home Assistant target.",
        )
    return ResolvedControl(
        action=request.action,
        service_calls=tuple(
            ControlServiceCall(
                domain=domain,
                service=service,
                entity_ids=tuple(sorted(entity_ids)),
            )
            for (domain, service), entity_ids in sorted(calls_by_service.items())
        ),
        target=request.target,
        resolution=resolution,
    )


def _service_for(domain: str, action: str) -> str | None:
    """Return the allowlisted Home Assistant service for a domain and action."""
    return ALLOWED_SERVICES.get(domain, {}).get(action)


def _normalise_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return resolver rows with stable lowercase keys and comparison values."""
    normalised: list[dict[str, Any]] = []
    for source in rows:
        row = {str(key).lower(): value for key, value in source.items()}
        entity_id = _normalise(row.get("entity_id"))
        if not entity_id or "." not in entity_id:
            continue
        domain, object_id = entity_id.split(".", 1)
        normalised.append(
            {
                "alias_name": _normalise(row.get("alias_name")),
                "entity_id": entity_id,
                "domain": _normalise(row.get("domain")) or domain,
                "object_id": _normalise(row.get("object_id")) or object_id,
                "entity_name": _normalise(row.get("entity_name")),
                "original_name": _normalise(row.get("original_name")),
                "friendly_name": _normalise(row.get("friendly_name")),
                "device_name": _normalise(row.get("device_name")),
                "area_name": _normalise(row.get("area_name")),
                "area_aliases": _json_names(row.get("area_aliases")),
            }
        )
    return normalised


def _matches_exact_name(row: Mapping[str, Any], request: ControlRequest) -> bool:
    """Return whether a row exactly matches an entity or device identifier."""
    target = _normalise(request.target)
    names = {
        row["entity_id"],
        row["object_id"],
        row["entity_name"],
        row["original_name"],
        row["friendly_name"],
        row["device_name"],
    }
    return target in names


def _matches_area(row: Mapping[str, Any], request: ControlRequest) -> bool:
    """Return whether a row belongs to an exact requested area."""
    target = _area_target(request.target, request.requested_domain)
    area_names = {row["area_name"], *row["area_aliases"]}
    return target in area_names and _domain_matches(row, request.requested_domain)


def _domain_matches(row: Mapping[str, Any], requested_domain: str | None) -> bool:
    """Return whether a row is eligible for requested terminology."""
    domain = row["domain"]
    if requested_domain is None:
        return domain in ALLOWED_SERVICES
    if requested_domain == domain:
        return True
    if requested_domain == "light" and domain == "switch":
        identifying_text = " ".join(
            str(row.get(key) or "")
            for key in (
                "object_id",
                "entity_name",
                "original_name",
                "friendly_name",
                "device_name",
            )
        )
        return bool(re.search(r"\b(?:lamp|light)s?\b", identifying_text))
    return False


def _requested_domain(target: str, action: str) -> str | None:
    """Infer only explicitly named domain terminology from a parsed target."""
    words = target.split()
    for word in words:
        domain = _DOMAIN_TERMS.get(word)
        if domain is not None:
            return domain
    if action == "activate":
        return "scene"
    return None


def _area_target(target: str, requested_domain: str | None) -> str:
    """Remove one trailing device noun when resolving an exact area name."""
    words = _normalise(target).split()
    if words and _DOMAIN_TERMS.get(words[-1]) == requested_domain:
        words.pop()
    return " ".join(words)


def _json_names(value: Any) -> set[str]:
    """Return canonical names from an area aliases JSON value."""
    if value is None:
        return set()
    if hasattr(value, "read"):
        value = value.read()
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return set()
    if not isinstance(value, list):
        return set()
    return {_normalise(item) for item in value if _normalise(item)}


def _deduplicate_entities(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate view rows introduced by multi-entity aliases."""
    by_entity: dict[str, dict[str, Any]] = {}
    for row in rows:
        by_entity.setdefault(row["entity_id"], row)
    return list(by_entity.values())


def _normalise(value: Any) -> str:
    """Return canonical lowercase text for deterministic comparisons."""
    text = re.sub(r"[^a-z0-9_.\s-]", " ", str(value or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _normalise_target(value: Any) -> str:
    """Normalise spoken target text while retaining internal entity-ID dots."""
    return _normalise(value).strip(".- ")
