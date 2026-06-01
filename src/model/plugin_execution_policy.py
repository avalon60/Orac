"""Policy checks and provenance helpers for plugin execution."""
# Author: Clive Bostock
# Date: 2026-05-24
# Description: Classifies plugin action risk before loading plugin code.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from model.plugin_confirmation_broker import PluginConfirmationBroker
from model.plugin_confirmation_broker import PluginConfirmationDecision
from model.plugin_confirmation_broker import PluginConfirmationRequest
from model.plugin_routing.models import PluginExecutionPolicy, PluginManifest


SAFE_ACTION_TYPES = {"informational_read_only"}
KNOWN_ACTION_TYPES = {
    "informational_read_only",
    "external_read",
    "local_mutation",
    "external_mutation",
    "device_control",
    "privileged_system_action",
}


@dataclass(frozen=True)
class PluginPolicyDecision:
    """Represents the result of a plugin execution policy check."""

    allowed: bool
    status: str
    reason: str | None
    provenance: dict[str, Any]


def evaluate_plugin_policy(
    manifest: PluginManifest,
    *,
    meta: dict[str, Any] | None = None,
    confirmation_broker: PluginConfirmationBroker | None = None,
) -> PluginPolicyDecision:
    """Evaluate whether a plugin may execute for the current request."""
    policy = manifest.execution_policy or PluginExecutionPolicy(
        action_type="privileged_system_action",
        requires_confirmation=True,
        allowed_by_default=False,
        capabilities=manifest.capabilities,
        entitlements=manifest.entitlements,
        notes="Missing execution policy; failing closed.",
    )
    meta = meta if isinstance(meta, dict) else {}
    confirmation_meta = meta.get("plugin_confirmation")
    confirmation_meta = confirmation_meta if isinstance(confirmation_meta, dict) else {}

    action_type = str(policy.action_type or "").strip()
    if action_type not in KNOWN_ACTION_TYPES:
        reason = f"Unknown plugin action type '{action_type}'."
        return _decision(manifest, policy, allowed=False, status="denied", reason=reason)

    if policy.scaffold:
        reason = "Plugin is marked scaffold or experimental and is not control-capable."
        return _decision(manifest, policy, allowed=False, status="denied", reason=reason)

    if action_type in SAFE_ACTION_TYPES and policy.allowed_by_default:
        return _decision(manifest, policy, allowed=True, status="allowed", reason=None)

    if policy.allowed_by_default and not policy.requires_confirmation:
        return _decision(manifest, policy, allowed=True, status="allowed", reason=None)

    confirmation_decision: PluginConfirmationDecision | None = None
    if policy.requires_confirmation:
        confirmation_decision = _trusted_confirmation_decision(
            confirmation_broker=confirmation_broker,
            confirmation_meta=confirmation_meta,
            manifest=manifest,
            policy=policy,
        )
        if confirmation_decision is not None and confirmation_decision.confirmed:
            return _decision(
                manifest,
                policy,
                allowed=True,
                status="allowed",
                reason=None,
                confirmation_decision=confirmation_decision,
            )

        confirmation_request = (
            confirmation_broker.create_request(manifest, policy)
            if confirmation_broker is not None
            else None
        )
        reason = "Plugin action requires explicit confirmation before execution."
        return _decision(
            manifest,
            policy,
            allowed=False,
            status="requires_confirmation",
            reason=reason,
            confirmation_decision=confirmation_decision,
            confirmation_request=confirmation_request,
        )

    reason = "Plugin action is not allowed by the current execution policy."
    return _decision(manifest, policy, allowed=False, status="denied", reason=reason)


def _trusted_confirmation_decision(
    *,
    confirmation_broker: PluginConfirmationBroker | None,
    confirmation_meta: dict[str, Any],
    manifest: PluginManifest,
    policy: PluginExecutionPolicy,
) -> PluginConfirmationDecision | None:
    """Return broker-backed confirmation state, ignoring legacy policy claims."""
    if confirmation_broker is None:
        return None
    confirmation_id = confirmation_meta.get("confirmation_id")
    if confirmation_id is None:
        confirmation_id = confirmation_meta.get("id")
    return confirmation_broker.consume_confirmation(
        confirmation_id=str(confirmation_id or ""),
        manifest=manifest,
        policy=policy,
    )


def _decision(
    manifest: PluginManifest,
    policy: PluginExecutionPolicy,
    *,
    allowed: bool,
    status: str,
    reason: str | None,
    confirmation_decision: PluginConfirmationDecision | None = None,
    confirmation_request: PluginConfirmationRequest | None = None,
) -> PluginPolicyDecision:
    provenance = build_plugin_provenance(
        manifest,
        policy=policy,
        status=status,
        reason=reason,
    )
    if confirmation_decision is not None:
        provenance["confirmation"] = {
            "trusted": bool(confirmation_decision.confirmed),
            "status": confirmation_decision.status,
            "confirmation_id": confirmation_decision.confirmation_id,
            "reason": confirmation_decision.reason,
        }
    if confirmation_request is not None:
        provenance["confirmation_request"] = {
            "confirmation_id": confirmation_request.confirmation_id,
            "plugin_id": confirmation_request.plugin_id,
            "plugin_name": confirmation_request.plugin_name,
            "action_type": confirmation_request.action_type,
            "capabilities": confirmation_request.capabilities,
            "action_summary": confirmation_request.action_summary,
            "created_at": confirmation_request.created_at.isoformat(),
            "expires_at": confirmation_request.expires_at.isoformat(),
        }
    return PluginPolicyDecision(
        allowed=allowed,
        status=status,
        reason=reason,
        provenance=provenance,
    )


def build_plugin_provenance(
    manifest: PluginManifest,
    *,
    policy: PluginExecutionPolicy,
    status: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Build stable provenance metadata for plugin-handled responses."""
    provenance: dict[str, Any] = {
        "source": "plugin_execution",
        "plugin_id": manifest.plugin_id,
        "plugin_name": manifest.name,
        "action_type": policy.action_type,
        "status": status,
        "requires_confirmation": policy.requires_confirmation,
        "allowed_by_default": policy.allowed_by_default,
        "capabilities": tuple(policy.capabilities or manifest.capabilities),
        "entitlements": tuple(policy.entitlements or manifest.entitlements),
        "scaffold": bool(policy.scaffold),
    }
    if reason:
        provenance["reason"] = reason
    if policy.notes:
        provenance["notes"] = policy.notes
    return provenance


def plugin_policy_message(decision: PluginPolicyDecision) -> str:
    """Return user-facing text for a denied or confirmation-required plugin action."""
    plugin_name = str(decision.provenance.get("plugin_name") or "This plugin")
    action_type = str(decision.provenance.get("action_type") or "unknown")
    if decision.status == "requires_confirmation":
        return (
            f"{plugin_name} needs explicit confirmation before it can run "
            f"the requested {action_type} action."
        )
    return (
        f"{plugin_name} is not allowed to run the requested {action_type} "
        "action under the current plugin policy."
    )
