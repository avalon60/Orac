"""Define immutable dataset, query and result contracts."""

# Author: Clive Bostock
# Date: 08-Nov-2026
# Description: Transport-neutral relational query contracts.
# Purpose: Bound metadata, generation and result representations.
# Usage: Imported by Core relational query services.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


class QueryDenied(ValueError):
    """Report a safe, content-free query rejection code."""


@dataclass(frozen=True)
class Dataset:
    """Describe a versioned projection, never a database privilege grant."""

    dataset_id: str
    plugin_id: str
    capability_id: str
    metadata_version: str
    views: Mapping[str, tuple[str, ...]]
    semantics: tuple[str, ...] = ()
    # Enablement requires a separate operator-reviewed live release gate.
    verified: bool = False


@dataclass(frozen=True)
class ValidatedQuery:
    """Carry only canonical, revalidated SQL and scalar binds to execution."""

    sql: str
    binds: Mapping[str, Any]


@dataclass(frozen=True)
class QueryResult:
    """Return bounded data with explicit truncation and dataset provenance."""

    status: str
    dataset_id: str
    metadata_version: str
    columns: tuple[str, ...] = ()
    rows: tuple[tuple[Any, ...], ...] = ()
    sql: str = ""
    truncated: bool = False
    message: str = ""
    provenance: Mapping[str, Any] = field(default_factory=dict)
    catalogue_answer: str = ""
    general_knowledge_answer: str = ""
    answer_status: str = "unavailable"
