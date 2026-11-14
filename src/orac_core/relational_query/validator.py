"""Validate a deliberately small Oracle SELECT language before execution."""

# Author: Clive Bostock
# Date: 08-Nov-2026
# Description: Fail-closed SQLGlot node, argument, source and column validation.
# Purpose: Restrict generated queries to one dataset's explicit projections.
# Usage: SQLValidator(dataset).validate(sql, binds).
from __future__ import annotations

import re
from typing import Any, Mapping

import sqlglot
from sqlglot import exp
from sqlglot.errors import ErrorLevel
from sqlglot.optimizer.scope import Scope, traverse_scope

from .models import Dataset, QueryDenied, ValidatedQuery

# Pinning alone is not a security control: every node AND populated argument is
# explicitly reviewed here. New parser representations remain denied.
_PIN = "27.28.1"
_ARGS = {
    "Select": {
        "expressions",
        "from",
        "joins",
        "where",
        "group",
        "having",
        "order",
        "limit",
        "distinct",
        "with",
        "connect",
    },
    "From": {"this"},
    "Table": {"this", "db", "alias"},
    "Identifier": {"this", "quoted"},
    "TableAlias": {"this"},
    "Column": {"this", "table"},
    "Alias": {"this", "alias"},
    "With": {"expressions"},
    "CTE": {"this", "alias"},
    "Subquery": {"this", "alias"},
    "Exists": {"this"},
    "Join": {"this", "on", "side", "kind"},
    "Where": {"this"},
    "Having": {"this"},
    "Group": {"expressions"},
    "Order": {"expressions"},
    "Ordered": {"this", "desc", "nulls_first"},
    "Fetch": {"direction", "count", "limit_options"},
    "LimitOptions": {"rows"},
    "Distinct": {"expressions"},
    "Literal": {"this", "is_string"},
    "Placeholder": {"this"},
    "Boolean": {"this"},
    "Null": set(),
    "Paren": {"this"},
    "Not": {"this"},
    "Neg": {"this"},
    "Between": {"this", "low", "high"},
    "In": {"this", "expressions", "query"},
    "Star": set(),
    "Count": {"this", "expressions", "big_int"},
    "Sum": {"this"},
    "Min": {"this"},
    "Max": {"this"},
    "Avg": {"this"},
    "Lower": {"this"},
    "Upper": {"this"},
    "Length": {"this"},
    "Coalesce": {"this", "expressions", "is_nvl"},
    "Connect": {"start", "connect", "nocycle"},
    "Prior": {"this"},
}
for _binary in (
    "EQ",
    "NEQ",
    "GT",
    "GTE",
    "LT",
    "LTE",
    "And",
    "Or",
    "Is",
    "Like",
    "Add",
    "Sub",
    "Mul",
    "Div",
):
    _ARGS[_binary] = {"this", "expression"}
_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]*", re.I)


class SQLValidator:
    """Validate and canonicalise against an immutable dataset projection."""

    def __init__(self, dataset: Dataset) -> None:
        """Keep the host-selected dataset, independent of generated SQL."""
        self.dataset = dataset

    def validate(self, sql: str, binds: Mapping[str, Any]) -> ValidatedQuery:
        """Reject unsupported syntax and return only revalidated canonical SQL."""
        if sqlglot.__version__ != _PIN:
            raise QueryDenied("PARSER_VERSION_UNVERIFIED")
        if not isinstance(sql, str) or not sql or len(sql.encode()) > 16384:
            raise QueryDenied("SQL_SIZE")
        # Comments/hints and database links are never part of this language.
        if any(token in sql for token in ("--", "/*", "*/", "@", ";")):
            raise QueryDenied("SQL_SYNTAX")
        if not isinstance(binds, dict) or len(binds) > 100:
            raise QueryDenied("BINDS")
        for name, value in binds.items():
            if not _IDENTIFIER.fullmatch(name) or type(value) not in (
                str,
                int,
                float,
                bool,
                type(None),
            ):
                raise QueryDenied("BINDS")
            if isinstance(value, str) and len(value) > 2048:
                raise QueryDenied("BINDS")
        try:
            tree = self._parse(sql)
            self._check(tree, binds)
            canonical = tree.sql(dialect="oracle", pretty=False)
            self._check(self._parse(canonical), binds)
        except QueryDenied:
            raise
        except Exception:
            raise QueryDenied("SQL_UNSUPPORTED") from None
        return ValidatedQuery(canonical, dict(binds))

    @staticmethod
    def _parse(sql: str) -> exp.Select:
        trees = sqlglot.parse(sql, read="oracle", error_level=ErrorLevel.RAISE)
        if len(trees) != 1 or not isinstance(trees[0], exp.Select):
            raise QueryDenied("SELECT_REQUIRED")
        return trees[0]

    def _check(self, tree: exp.Select, binds: Mapping[str, Any]) -> None:
        placeholders = set()
        for node in tree.walk():
            kind = type(node).__name__
            if kind not in _ARGS or any(
                key not in _ARGS[kind] and value not in (None, False, [], "")
                for key, value in node.args.items()
            ):
                raise QueryDenied("SQL_CONSTRUCT")
            if node.comments:
                raise QueryDenied("SQL_COMMENTS")
            if isinstance(node, exp.Identifier) and (
                node.args.get("quoted") or not _IDENTIFIER.fullmatch(node.name)
            ):
                raise QueryDenied("SQL_IDENTIFIER")
            if isinstance(node, exp.Placeholder):
                placeholders.add(node.name)
            if isinstance(node, exp.Star) and not isinstance(node.parent, exp.Count):
                raise QueryDenied("EXPLICIT_COLUMNS_REQUIRED")
            if isinstance(node, exp.Join):
                if (
                    node.args.get("kind") not in (None, "", "INNER")
                    or node.args.get("side") not in (None, "", "LEFT", "RIGHT")
                    or not node.args.get("on")
                ):
                    raise QueryDenied("SQL_JOIN")
            if isinstance(node, exp.Fetch):
                count = node.args.get("count")
                if (
                    not isinstance(count, exp.Literal)
                    or count.is_string
                    or not count.this.isdigit()
                    or not 1 <= int(count.this) <= 500
                ):
                    raise QueryDenied("SQL_FETCH")
        if placeholders != set(binds):
            raise QueryDenied("BINDS_MISMATCH")
        for scope in traverse_scope(tree):
            self._scope(scope)

    def _scope(self, scope: Scope) -> None:
        def sources(current: Scope) -> dict[str, set[str]]:
            available: dict[str, set[str]] = {}
            for alias, (_, source) in current.selected_sources.items():
                if isinstance(source, exp.Table):
                    full = f"{source.db}.{source.name}".lower()
                    if full not in self.dataset.views:
                        raise QueryDenied("DATASET_OBJECT")
                    available[alias.lower()] = set(self.dataset.views[full])
                elif isinstance(source, Scope):
                    available[alias.lower()] = {
                        name.lower() for name in source.expression.named_selects
                    }
                else:
                    raise QueryDenied("DATASET_SOURCE")
            return available

        available = sources(scope)
        if not available:
            raise QueryDenied("DATASET_SOURCE")
        # Oracle resolves the nearest lexical scope first. Outer sources must
        # not manufacture ambiguity in an otherwise unambiguous local column.
        levels = [available]
        parent = scope.parent if scope.can_be_correlated else None
        while parent is not None:
            levels.append(sources(parent))
            if not parent.can_be_correlated:
                break
            parent = parent.parent
        aliases = {
            item.alias.lower()
            for item in scope.expression.expressions
            if isinstance(item, exp.Alias)
        }
        for column in scope.expression.find_all(exp.Column):
            if column.find_ancestor(exp.Select) is not scope.expression:
                continue
            name, table = column.name.lower(), column.table.lower()
            if name == "level" and scope.expression.args.get("connect"):
                continue
            allowed = False
            if table:
                for level in levels:
                    if table in level:
                        # A local alias shadows the outer alias even when it
                        # does not expose the requested column.
                        allowed = name in level[table]
                        break
            else:
                for level in levels:
                    matches = sum(name in columns for columns in level.values())
                    if matches:
                        allowed = matches == 1
                        break
                if isinstance(column.parent, exp.Ordered) and name in aliases:
                    allowed = True
            if not allowed:
                raise QueryDenied("DATASET_COLUMN")
        connect = scope.expression.args.get("connect")
        if connect is not None:
            self._hierarchy(connect, available)

    @staticmethod
    def _hierarchy(connect: exp.Connect, available: dict[str, set[str]]) -> None:
        # Restrict hierarchy to ONE ownership-bearing projection. Requiring the
        # exact shape prevents OR branches from weakening ownership/depth checks.
        if len(available) != 1 or not connect.args.get("nocycle"):
            raise QueryDenied("HIERARCHY")
        columns = next(iter(available.values()))
        condition = connect.args.get("connect")
        expected = "prior opening_id = parent_opening_id AND level <= 32"
        if "variation_id" in columns:
            # Variation owners must remain identical along each edge, including
            # nullable opening/gambit identities. Explicit OR/NULL form required.
            expected = (
                "prior variation_id = parent_variation_id AND "
                "(prior opening_id = opening_id OR (prior opening_id IS NULL AND opening_id IS NULL)) AND "
                "(prior gambit_id = gambit_id OR (prior gambit_id IS NULL AND gambit_id IS NULL)) AND level <= 32"
            )
        expected_tree = (
            sqlglot.parse_one(
                "select name from x connect by nocycle " + expected, read="oracle"
            )
            .args["connect"]
            .args["connect"]
        )
        if condition != expected_tree or not connect.args.get("start"):
            raise QueryDenied("HIERARCHY")
