"""Validate declarative plugin datasets and collect projection-only metadata."""

# Author: Clive Bostock
# Date: 08-Nov-2026
# Description: Versioned dataset declaration and Oracle dictionary projection.
# Purpose: Reject executable or privileged manifest dataset configuration.
# Usage: parse_datasets(manifest_field, plugin_id, capabilities, schema_names).
from __future__ import annotations

import re
from typing import Any, Callable

from .deadline import bounded_cursor, limit_session
from .models import Dataset, QueryDenied
from .reviewed import ReviewedSnapshot

_NAME = re.compile(r"[a-z][a-z0-9_]*")
_ID = re.compile(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*")


def parse_datasets(
    value: Any, plugin_id: str, capabilities: tuple[str, ...], schemas: tuple[str, ...]
) -> tuple[Dataset, ...]:
    """Validate optional declarations with no SQL, grants or enablement flags."""
    if not isinstance(value, list):
        raise ValueError("query_datasets must be a list")
    datasets = []
    seen = set()
    for item in value:
        if not isinstance(item, dict) or set(item) != {
            "version",
            "dataset_id",
            "capability_id",
            "metadata_version",
            "views",
        }:
            raise ValueError("query_datasets declaration fields invalid")
        identifier, capability = item["dataset_id"], item["capability_id"]
        if (
            item["version"] != 1
            or not isinstance(identifier, str)
            or not _ID.fullmatch(identifier)
            or not identifier.startswith(plugin_id + ".")
            or identifier in seen
        ):
            raise ValueError("query_datasets identity invalid")
        if (
            capability not in capabilities
            or not isinstance(item["metadata_version"], str)
            or not item["metadata_version"]
        ):
            raise ValueError("query_datasets capability/version invalid")
        views = item["views"]
        if not isinstance(views, dict) or not views or len(views) > 32:
            raise ValueError("query_datasets views invalid")
        for name, columns in views.items():
            parts = name.split(".")
            if (
                len(parts) != 2
                or parts[0] not in schemas
                or any(not _NAME.fullmatch(part) for part in parts)
            ):
                raise ValueError("query_datasets view ownership invalid")
            if (
                not isinstance(columns, list)
                or not columns
                or len(columns) != len(set(columns))
                or any(
                    not isinstance(column, str) or not _NAME.fullmatch(column)
                    for column in columns
                )
            ):
                raise ValueError("query_datasets columns invalid")
        seen.add(identifier)
        datasets.append(
            Dataset(
                identifier,
                plugin_id,
                capability,
                item["metadata_version"],
                {name: tuple(columns) for name, columns in views.items()},
            )
        )
    return tuple(datasets)


class MetadataCatalogue:
    """Build a filtered dictionary snapshot after Core eligibility succeeds."""

    def __init__(self, session_factory: Callable[[], Any]) -> None:
        """Store the dedicated least-privilege query metadata connection factory."""
        self._factory = session_factory

    def load(
        self, dataset: Dataset, review: ReviewedSnapshot | None = None
    ) -> dict[str, Any]:
        """Read only declared view/column comments and exact projected constraints."""
        session = self._factory()
        try:
            output = {
                "dataset_id": dataset.dataset_id,
                "metadata_version": dataset.metadata_version,
                "views": {},
                "semantics": list(dataset.semantics),
            }
            sources: dict[tuple[str, str], list[str]] = {}
            with bounded_cursor(session) as cursor:
                cursor.execute("select sys_context('userenv','session_user') from dual")
                if str(cursor.fetchone()[0]).upper() != "ORAC_PLUGIN":
                    raise QueryDenied("EXECUTOR_IDENTITY")
                for name, allowed in dataset.views.items():
                    owner, view = name.upper().split(".")
                    cursor.execute(
                        "select column_name, data_type from all_tab_columns where owner=:owner and table_name=:view_name order by column_id",
                        {"owner": owner, "view_name": view},
                    )
                    columns = {
                        str(column).lower(): str(kind)
                        for column, kind in cursor.fetchall()
                    }
                    if set(columns) != set(allowed):
                        raise QueryDenied("CATALOGUE_DRIFT")
                    cursor.execute(
                        "select column_name, comments from all_col_comments where owner=:owner and table_name=:view_name",
                        {"owner": owner, "view_name": view},
                    )
                    comments = {
                        str(column).lower(): str(comment or "")[:2048]
                        for column, comment in cursor.fetchall()
                        if str(column).lower() in allowed
                    }
                    cursor.execute(
                        "select comments from all_tab_comments where owner=:owner and table_name=:view_name",
                        {"owner": owner, "view_name": view},
                    )
                    comment_row = cursor.fetchone()
                    cursor.execute(
                        "select referenced_owner, referenced_name, referenced_type, referenced_link_name from all_dependencies where owner=:owner and name=:view_name and type='VIEW'",
                        {"owner": owner, "view_name": view},
                    )
                    dependencies = cursor.fetchall()
                    if (
                        len(dependencies) != 1
                        or dependencies[0][2] != "TABLE"
                        or dependencies[0][3] is not None
                        or dependencies[0][0] != owner
                    ):
                        raise QueryDenied("CATALOGUE_DEPENDENCY_DRIFT")
                    source_owner, source_table = dependencies[0][:2]
                    if review is not None:
                        signature = review.value["views"][name]
                        actual = {
                            "columns": [
                                {"name": column, "type": kind}
                                for column, kind in columns.items()
                            ],
                            "source": {
                                "owner": source_owner.lower(),
                                "table": source_table.lower(),
                            },
                        }
                        if actual != signature:
                            raise QueryDenied("REVIEW_PROJECTION_DRIFT")
                    sources.setdefault((source_owner, source_table), []).append(name)
                    cursor.execute(
                        """select column_name, annotation_name, annotation_value
                             from all_annotations_usage
                            where annotation_owner=:owner
                              and ((object_name=:view_name and object_type='VIEW')
                                or (object_name=:source_table and object_type='TABLE'))
                              and domain_owner is null""",
                        {
                            "owner": owner,
                            "view_name": view,
                            "source_table": source_table,
                        },
                    )
                    annotation_keys = {
                        "display_name",
                        "plural_display_name",
                        "semantic_role",
                        "data_kind",
                        "unit",
                        "sensitivity",
                        "ai_queryable",
                        "ai_synonyms",
                    }
                    annotations = []
                    for column, key, value in cursor.fetchall():
                        if (column is None or str(column).lower() in allowed) and str(
                            key
                        ).lower() in annotation_keys:
                            annotations.append(
                                {
                                    "column": str(column).lower() if column else None,
                                    "key": str(key).lower(),
                                    "value": str(value or "")[:2048],
                                }
                            )
                    output["views"][name] = {
                        "annotations": annotations,
                        "columns": {
                            column: {
                                "type": columns[column],
                                "comment": comments.get(column, ""),
                            }
                            for column in allowed
                        },
                        "comment": (
                            str(comment_row[0] or "")[:4096] if comment_row else ""
                        ),
                    }
                if review is not None:
                    output["relationships"] = review.value["relationships"]
                    output["keys"] = review.value["keys"]
                    output["review_id"] = review.review_id
                    return output
                relationships = []
                keys = []
                for (owner, table), view_names in sources.items():
                    cursor.execute(
                        """
                        select c.constraint_name, c.constraint_type, cc.column_name, cc.position,
                               rc.owner, rc.table_name, rcc.column_name
                          from all_constraints c
                          join all_cons_columns cc on cc.owner=c.owner and cc.constraint_name=c.constraint_name
                          left join all_constraints rc on rc.owner=c.r_owner and rc.constraint_name=c.r_constraint_name
                          left join all_cons_columns rcc on rcc.owner=rc.owner and rcc.constraint_name=rc.constraint_name and rcc.position=cc.position
                         where c.owner=:owner and c.table_name=:table_name
                           and c.constraint_type in ('P','U','R') and c.status='ENABLED' and c.validated='VALIDATED'
                         order by c.constraint_name,cc.position
                    """,
                        {"owner": owner, "table_name": table},
                    )
                    groups: dict[str, list] = {}
                    for row in cursor.fetchall():
                        groups.setdefault(row[0], []).append(row)
                    for view_name in view_names:
                        for rows in groups.values():
                            columns = [str(row[2]).lower() for row in rows]
                            if not set(columns) <= set(dataset.views[view_name]):
                                continue
                            if rows[0][1] in ("P", "U"):
                                keys.append(
                                    {
                                        "view": view_name,
                                        "columns": columns,
                                        "kind": rows[0][1],
                                    }
                                )
                            else:
                                targets = sources.get((rows[0][4], rows[0][5]), [])
                                target_columns = [str(row[6]).lower() for row in rows]
                                for target in targets:
                                    if set(target_columns) <= set(
                                        dataset.views[target]
                                    ):
                                        relationships.append(
                                            {
                                                "view": view_name,
                                                "columns": columns,
                                                "target_view": target,
                                                "target_columns": target_columns,
                                            }
                                        )
                output["relationships"] = relationships
                output["keys"] = keys
            return output
        finally:
            session.close()
