"""Validate immutable operator-reviewed projection metadata without owner grants."""

# Author: Clive Bostock
# Date: 12-Nov-2026
# Description: Bind projected keys and relationships to the reviewed dataset identity.
# Purpose: Reject stale, malformed or overbroad constraint snapshots.
# Usage: Core runtime validates evidence_json.projected_metadata before metadata disclosure.
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from .models import Dataset, QueryDenied


@dataclass(frozen=True)
class ReviewedSnapshot:
    """Carry one validated immutable review and its canonical content digest."""

    value: dict[str, Any]
    digest: str

    @property
    def review_id(self) -> str:
        """Return the operator-assigned immutable review identity."""
        return self.value["review_id"]


def validate_snapshot(
    value: Any, dataset: Dataset, manifest_hash: str
) -> ReviewedSnapshot:
    """Validate a bounded review against the exact installed dataset declaration.

    Args:
        value: Parsed projected_metadata object from the verified Core catalogue.
        dataset: Current host-validated manifest declaration.
        manifest_hash: Current installed manifest fingerprint.

    Returns:
        Validated metadata and canonical SHA-256 digest.

    Raises:
        QueryDenied: If identities, projections, keys or edges are malformed.
    """

    def deny() -> None:
        raise QueryDenied("REVIEW_METADATA_INVALID")

    def fields(item: Any, expected: set[str]) -> None:
        if not isinstance(item, dict) or set(item) != expected:
            deny()

    def columns(item: Any, view: str) -> tuple[str, ...]:
        if not isinstance(item, list) or not 1 <= len(item) <= 32:
            deny()
        if any(
            not isinstance(col, str) or col not in dataset.views[view] for col in item
        ):
            deny()
        if len(set(item)) != len(item):
            deny()
        return tuple(item)

    fields(
        value,
        {
            "format",
            "dataset_id",
            "metadata_version",
            "manifest_hash",
            "review_id",
            "views",
            "keys",
            "relationships",
        },
    )
    if type(value["format"]) is not int or value["format"] != 1:
        deny()
    if (value["dataset_id"], value["metadata_version"], value["manifest_hash"]) != (
        dataset.dataset_id,
        dataset.metadata_version,
        manifest_hash,
    ):
        deny()
    if not isinstance(value["review_id"], str) or not re.fullmatch(
        r"[A-Za-z0-9._-]{1,128}", value["review_id"]
    ):
        deny()
    views = value["views"]
    if (
        not isinstance(views, dict)
        or set(views) != set(dataset.views)
        or not 1 <= len(views) <= 32
    ):
        deny()
    for view, projection in views.items():
        fields(projection, {"columns", "source"})
        fields(projection["source"], {"owner", "table"})
        source = projection["source"]
        if (
            source["owner"] != view.split(".")[0]
            or not isinstance(source["table"], str)
            or not re.fullmatch(r"[a-z][a-z0-9_]*", source["table"])
        ):
            deny()
        signature = projection["columns"]
        if not isinstance(signature, list) or len(signature) != len(
            dataset.views[view]
        ):
            deny()
        for column, declared in zip(signature, dataset.views[view]):
            fields(column, {"name", "type"})
            if (
                column["name"] != declared
                or not isinstance(column["type"], str)
                or not re.fullmatch(r"[A-Z][A-Z0-9_ ()]{0,127}", column["type"])
            ):
                deny()
    keys, edges = value["keys"], value["relationships"]
    if (
        not isinstance(keys, list)
        or len(keys) > 256
        or not isinstance(edges, list)
        or len(edges) > 512
    ):
        deny()
    unique_keys = set()
    for key in keys:
        fields(key, {"view", "columns", "kind"})
        if (
            not isinstance(key["view"], str)
            or key["view"] not in views
            or key["kind"] not in ("P", "U")
        ):
            deny()
        identity = (key["view"], columns(key["columns"], key["view"]), key["kind"])
        if identity in unique_keys:
            deny()
        unique_keys.add(identity)
    unique_edges = set()
    for edge in edges:
        fields(edge, {"view", "columns", "target_view", "target_columns"})
        if any(
            not isinstance(edge[key], str) or edge[key] not in views
            for key in ("view", "target_view")
        ):
            deny()
        source_cols = columns(edge["columns"], edge["view"])
        target_cols = columns(edge["target_columns"], edge["target_view"])
        if len(source_cols) != len(target_cols) or not any(
            key[0] == edge["target_view"] and key[1] == target_cols
            for key in unique_keys
        ):
            deny()
        identity = (edge["view"], source_cols, edge["target_view"], target_cols)
        if identity in unique_edges:
            deny()
        unique_edges.add(identity)
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError):
        deny()
    if len(encoded) > 131072:
        deny()
    return ReviewedSnapshot(value, hashlib.sha256(encoded).hexdigest())
