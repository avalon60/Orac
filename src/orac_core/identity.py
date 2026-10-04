"""Define reserved Orac logical principals and identity safeguards."""

# Author: Clive Bostock
# Date: 2026-10-03
# Description: Centralise reserved non-interactive Orac principal handling.

SYSTEM_PREFERENCE_PRINCIPAL = "system"
RESERVED_NON_INTERACTIVE_PRINCIPALS = frozenset({SYSTEM_PREFERENCE_PRINCIPAL})


def is_reserved_non_interactive_principal(username: str | None) -> bool:
    """Return whether a username represents a reserved non-login principal.

    Args:
        username: Candidate Orac username.

    Returns:
        True when the normalized username is reserved and non-interactive.
    """
    return str(username or "").strip().lower() in RESERVED_NON_INTERACTIVE_PRINCIPALS
