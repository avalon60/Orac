"""Dialogue interceptor for Home Assistant plugin routing."""
# Author: Clive Bostock
# Date: 17-Jul-2026
# Description: Maps Home Assistant dialogue metadata matches into route arguments.

from __future__ import annotations

from typing import Any, Mapping

from model.plugin_routing.interception import InterceptRule, PluginDialogInterceptor

from .control import parse_area_inventory_command, parse_area_list_command
from .light_control import parse_light_control_command
from .light_state_query import parse_light_state_query
from .sensor_query import parse_sensor_query


class HomeAssistantDialogInterceptor(PluginDialogInterceptor):
    """Build Home Assistant route arguments from core-owned metadata matches."""

    def build_arguments(
        self,
        *,
        rule: InterceptRule,
        captures: Mapping[str, str],
        original_text: str,
        normalised_text: str,
    ) -> Mapping[str, Any] | None:
        """Return route arguments for a matched Home Assistant rule."""
        if rule.route_id == "resync_home_assistant":
            return {}
        if rule.route_id == "control_device":
            return _control_arguments(rule, captures)
        if rule.route_id == "activate_scene":
            target = _capture(captures, "target")
            return {"action": "activate", "target": target} if target else None
        if rule.route_id == "control_light":
            request = parse_light_control_command(original_text)
            return {"light_control": request.to_payload()} if request else None
        if rule.route_id == "query_light_state":
            request = parse_light_state_query(original_text)
            return {"light_state_query": request.to_payload()} if request else None
        if rule.route_id == "query_sensor_state":
            request = parse_sensor_query(original_text)
            if request is None:
                return None
            return {
                "sensor_query": {
                    "intent": request.intent,
                    "areas": list(request.areas),
                    "sensor_role": request.sensor_role,
                }
            }
        if rule.route_id == "list_area_inventory":
            inventory = parse_area_inventory_command(original_text)
            if inventory is not None:
                return {"area_listing": {"mode": "areas"}}
            area_list = parse_area_list_command(original_text)
            if area_list is None:
                return None
            return {
                "area_listing": {
                    "mode": "area",
                    "area": area_list.area,
                    "requested_domain": area_list.requested_domain,
                }
            }
        return None


def _control_arguments(
    rule: InterceptRule,
    captures: Mapping[str, str],
) -> Mapping[str, Any] | None:
    """Return structured control arguments from captures and static metadata."""
    target = _capture(captures, "target")
    if not target:
        return None
    action = str(rule.arguments.get("action") or "").strip()
    state = _capture(captures, "state").casefold()
    if not action and state in {"on", "off"}:
        action = "turn_on" if state == "on" else "turn_off"
    if not action:
        return None
    return {
        "action": action,
        "target": target,
    }


def _capture(captures: Mapping[str, str], key: str) -> str:
    """Return one stripped named capture."""
    return str(captures.get(key) or "").strip()
