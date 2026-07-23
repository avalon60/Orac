"""Pure policy for determining runtime-eligible plugin registry rows."""

# Author: Clive Bostock
# Date: 19-Jul-2026
# Description: Owns plugin runtime eligibility independently from database adapters.

from __future__ import annotations

from typing import Any, Mapping


def plugin_registry_row_runtime_eligible(row: Mapping[str, Any]) -> bool:
    """Return whether a registry row passes every runtime eligibility gate.

    Args:
        row: Registry values exposed by the approved plugin registry view.

    Returns:
        ``True`` only when enablement, installation, configuration,
        dependencies, database deployment, and readiness all permit runtime
        use.
    """
    return (
        str(row.get("enabled") or "").upper() == "Y"
        and str(row.get("install_status") or "") == "success"
        and str(row.get("configuration_status") or "") in {"success", "not_required"}
        and str(row.get("dependency_status") or "") in {"success", "not_required"}
        and str(row.get("database_status") or "")
        in {"deployed", "already_deployed", "not_required", "optional_missing"}
        and str(row.get("readiness_status") or "") == "success"
    )
