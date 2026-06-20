"""Home Assistant plugin operational status models and redaction helpers."""
# Author: Clive Bostock
# Date: 20-Jun-2026
# Description: Builds redacted Home Assistant plugin status summaries.

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import re
from typing import Any, Mapping

__author__ = "Clive Bostock"
__date__ = "20-Jun-2026"
__description__ = "Builds redacted Home Assistant plugin status summaries."


PLUGIN_ID = "home_assistant"

_BEARER_RE = re.compile(r"\b(bearer)\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_URL_CREDENTIAL_RE = re.compile(
    r"\b([a-z][a-z0-9+.-]*://)([^/\s:@]+):([^@\s/]+)@",
    re.IGNORECASE,
)
_ASSIGNMENT_SECRET_RE = re.compile(
    r"\b(access[_-]?token|token|password|passwd|secret|api[_-]?key)"
    r"(\s*[:=]\s*)(['\"]?)[^'\"\s,;]+(['\"]?)",
    re.IGNORECASE,
)
_JSON_SECRET_RE = re.compile(
    r'("(?:access[_-]?token|token|password|passwd|secret|api[_-]?key)"\s*:\s*)"[^"]*"',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class HomeAssistantStatusSummary:
    """Redacted operational status for the Home Assistant plugin."""

    plugin_id: str
    service_running: bool | None
    api_reachable: bool | None
    last_startup_sync_at: Any | None
    last_startup_sync_status: str | None
    last_state_sync_at: Any | None
    last_state_sync_status: str | None
    last_areas_processed: int
    last_devices_processed: int
    last_entities_processed: int
    last_states_processed: int
    last_error_message_redacted: str | None
    updated_at: Any | None

    def as_dict(self) -> dict[str, Any]:
        """Return the summary as a serialisable dictionary."""
        return asdict(self)


def redact_sensitive_text(value: Any) -> str | None:
    """Return text with common credential shapes replaced by redaction markers."""
    if value is None:
        return None
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = _URL_CREDENTIAL_RE.sub(r"\1[redacted]@", text)
    text = _BEARER_RE.sub(r"\1 [redacted]", text)
    text = _JSON_SECRET_RE.sub(r'\1"[redacted]"', text)
    text = _ASSIGNMENT_SECRET_RE.sub(r"\1\2\3[redacted]\4", text)
    return text[:4000]


def summary_from_row(
    row: Mapping[str, Any] | None,
    *,
    service_running: bool | None = None,
    api_reachable: bool | None = None,
    last_error_message: str | None = None,
    updated_at: datetime | None = None,
) -> HomeAssistantStatusSummary:
    """Build a status summary from a database view row and runtime state."""
    values = {str(key).lower(): value for key, value in dict(row or {}).items()}
    error_message = last_error_message
    if error_message is None:
        error_message = values.get("last_error_message_redacted")
    return HomeAssistantStatusSummary(
        plugin_id=str(values.get("plugin_id") or PLUGIN_ID),
        service_running=_coalesce_bool(service_running, values.get("service_running")),
        api_reachable=_coalesce_bool(api_reachable, values.get("api_reachable")),
        last_startup_sync_at=values.get("last_startup_sync_at"),
        last_startup_sync_status=_optional_string(values.get("last_startup_sync_status")),
        last_state_sync_at=values.get("last_state_sync_at"),
        last_state_sync_status=_optional_string(values.get("last_state_sync_status")),
        last_areas_processed=_int_value(values.get("last_areas_processed")),
        last_devices_processed=_int_value(values.get("last_devices_processed")),
        last_entities_processed=_int_value(values.get("last_entities_processed")),
        last_states_processed=_int_value(values.get("last_states_processed")),
        last_error_message_redacted=redact_sensitive_text(error_message),
        updated_at=updated_at or values.get("updated_at"),
    )


def _optional_string(value: Any) -> str | None:
    """Return a stripped string or ``None``."""
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _int_value(value: Any) -> int:
    """Return a non-negative integer count."""
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _coalesce_bool(runtime_value: bool | None, database_value: Any) -> bool | None:
    """Prefer runtime booleans and parse database flags as fallback."""
    if runtime_value is not None:
        return runtime_value
    if database_value is None:
        return None
    if isinstance(database_value, bool):
        return database_value
    cleaned = str(database_value).strip().lower()
    if cleaned in {"y", "yes", "true", "1", "running", "reachable"}:
        return True
    if cleaned in {"n", "no", "false", "0", "stopped", "unreachable"}:
        return False
    return None
