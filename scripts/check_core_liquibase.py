"""Validate core Orac Liquibase formatted SQL and controller coverage."""
# Author: Clive Bostock
# Date: 22-Jun-2026
# Description: Checks that core schema SQL files are Liquibase-owned changesets.
# Purpose: Detect drift between core schema assets and Liquibase deployment.
# Usage: poetry run python scripts/check_core_liquibase.py

from __future__ import annotations

import argparse
from dataclasses import dataclass
import re
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


CORE_SCHEMAS = ("orac_core", "orac_api", "orac_code", "orac_apx_pub", "orac")
APEX_SCHEMA_DIRS = {"orac_ws", "orac_apps"}
HARD_OBJECT_DIRS = {
    "table",
    "sequence",
    "index",
    "constraint_pk",
    "constraint_uc",
    "constraint_other",
    "constraint_fk",
}
PLSQL_DIRS = {
    "package_spec",
    "package_body",
    "trigger",
    "procedure",
    "function",
    "type_spec",
    "type_body",
    "post_install",
}
ROLLBACK_REQUIRED_DIRS = {
    "table",
    "sequence",
    "index",
    "constraint_pk",
    "constraint_uc",
    "constraint_other",
    "constraint_fk",
    "package_spec",
    "package_body",
    "view",
    "synonym",
    "grant",
    "privilege",
    "trigger",
    "procedure",
    "function",
    "type_spec",
    "type_body",
    "seed_data",
}
TRACKING_TABLE_KEYS = {
    "databaseChangeLogTableName",
    "databaseChangeLogLockTableName",
}
LIQUIBASE_NAMESPACE = {"db": "http://www.liquibase.org/xml/ns/dbchangelog"}
CHANGESET_PATTERN = re.compile(r"^--changeset\s+(\S+):(\S+)(.*)$", re.MULTILINE)
FORCE_VIEW_PATTERN = re.compile(
    r"\bcreate\s+or\s+replace\s+force\s+view\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Changeset:
    """Represents one formatted SQL changeset directive."""

    author: str
    changeset_id: str
    attributes: str
    line: str


def default_project_root() -> Path:
    """Return the project root inferred from this script location."""
    return Path(__file__).resolve().parent.parent


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser."""
    parser = argparse.ArgumentParser(
        description="Validate core Orac Liquibase formatted SQL coverage.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=default_project_root(),
        help="Project root. Default: inferred from the script location.",
    )
    return parser


def schema_root(root: Path) -> Path:
    """Return the schema deployment root."""
    return root / "resources/db/schema"


def product_controller(root: Path) -> Path:
    """Return the active production controller path."""
    return schema_root(root) / "productController.xml"


def core_schema_sql_files(root: Path) -> set[Path]:
    """Return canonical core schema SQL files that Liquibase must own."""
    files: set[Path] = set()
    for schema in CORE_SCHEMAS:
        for path in sorted((schema_root(root) / schema).glob("*/*.sql")):
            files.add(path.resolve())
    return files


def stale_apex_schema_dirs(root: Path) -> list[Path]:
    """Return old APEX export directories found under schema bundles."""
    stale_dirs: list[Path] = []
    for schema in CORE_SCHEMAS:
        schema_dir = schema_root(root) / schema
        for apex_dir in sorted(APEX_SCHEMA_DIRS):
            path = schema_dir / apex_dir
            if path.exists():
                stale_dirs.append(path)
    return stale_dirs


def parse_xml(path: Path) -> ET.Element:
    """Parse a Liquibase XML controller and return its document root."""
    return ET.parse(path).getroot()


def resolve_relative(source: Path, raw_path: str) -> Path:
    """Resolve a controller include path relative to the controller file."""
    return (source.parent / raw_path).resolve()


def controller_xml_files(root: Path) -> list[Path]:
    """Return active core controller XML files from the schema-root chain."""
    controllers = [product_controller(root).resolve()]
    if not controllers[0].exists():
        return controllers
    document = parse_xml(controllers[0])
    for include in document.findall("./db:include", LIQUIBASE_NAMESPACE):
        raw_file = include.attrib.get("file")
        if raw_file:
            controllers.append(resolve_relative(controllers[0], raw_file))
    return controllers


def reachable_sql_files(root: Path) -> set[Path]:
    """Return SQL files reachable from productController.xml."""
    reachable: set[Path] = set()
    controllers = controller_xml_files(root)
    for controller in controllers:
        if not controller.exists():
            continue
        document = parse_xml(controller)
        for sql_file in document.findall(".//db:sqlFile", LIQUIBASE_NAMESPACE):
            raw_path = sql_file.attrib.get("path", "")
            if raw_path:
                reachable.add(resolve_relative(controller, raw_path))
        for include in document.findall(".//db:include", LIQUIBASE_NAMESPACE):
            raw_file = include.attrib.get("file", "")
            if raw_file.endswith(".sql"):
                reachable.add(resolve_relative(controller, raw_file))
        for include_all in document.findall(".//db:includeAll", LIQUIBASE_NAMESPACE):
            raw_path = include_all.attrib.get("path", "")
            if not raw_path:
                continue
            directory = resolve_relative(controller, raw_path)
            if directory.is_dir():
                reachable.update(path.resolve() for path in sorted(directory.glob("*.sql")))
    return reachable


def liquibase_core_properties(root: Path) -> Path:
    """Return the core Liquibase properties path."""
    return root / "resources/db/liquibase/liquibase-core.properties"


def configured_tracking_table_keys(properties_path: Path) -> set[str]:
    """Return custom tracking table keys configured in the properties file."""
    configured: set[str] = set()
    for raw_line in properties_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key in TRACKING_TABLE_KEYS:
            configured.add(key)
    return configured


def changesets(text: str) -> list[Changeset]:
    """Return formatted SQL changeset directives from text."""
    return [
        Changeset(
            author=match.group(1),
            changeset_id=match.group(2),
            attributes=match.group(3),
            line=match.group(0),
        )
        for match in CHANGESET_PATTERN.finditer(text)
    ]


def has_formatted_sql_header(text: str) -> bool:
    """Return whether text begins with the formatted SQL header."""
    lines = text.splitlines()
    return bool(lines) and lines[0].strip().lower() == "--liquibase formatted sql"


def object_dir(path: Path) -> str:
    """Return the object-type directory for a schema SQL file."""
    return path.parent.name


def owning_schema(path: Path) -> str:
    """Return the owning schema directory for a schema SQL file."""
    return path.parent.parent.name


def same_schema_view_references(text: str, schema_name: str) -> bool:
    """Return whether view SQL references another object in its own schema."""
    return bool(
        re.search(
            rf"\b(from|join)\s+{re.escape(schema_name)}\.",
            text,
            flags=re.IGNORECASE,
        )
    )


def validate_sql_file(path: Path, root: Path) -> list[str]:
    """Validate one Liquibase-owned core SQL file."""
    issues: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    relative = path.relative_to(root)
    directory = object_dir(path)
    file_changesets = changesets(text)
    schema_name = owning_schema(path)

    if not has_formatted_sql_header(text):
        issues.append(f"{relative}: Liquibase-owned SQL lacks --liquibase formatted sql")
    if not file_changesets:
        issues.append(f"{relative}: Liquibase-owned SQL lacks a --changeset")
        return issues

    for changeset in file_changesets:
        attributes = changeset.attributes
        if "context:core" not in attributes:
            issues.append(f"{relative}: {changeset.changeset_id} lacks context:core")
        if "labels:core" not in attributes:
            issues.append(f"{relative}: {changeset.changeset_id} lacks labels:core")

        if directory in HARD_OBJECT_DIRS:
            if "runOnChange:true" in attributes:
                issues.append(
                    f"{relative}: hard-object changeset {changeset.changeset_id} "
                    "uses runOnChange:true"
                )
            if "--preconditions onFail:HALT onError:HALT" not in text:
                issues.append(
                    f"{relative}: hard-object changeset {changeset.changeset_id} "
                    "lacks authoritative preconditions"
                )

        if directory in PLSQL_DIRS:
            if "splitStatements:false" not in attributes or "endDelimiter:/" not in attributes:
                issues.append(
                    f"{relative}: PL/SQL changeset {changeset.changeset_id} "
                    "lacks splitStatements:false endDelimiter:/"
                )

    if (
        directory == "view"
        and same_schema_view_references(text, schema_name)
        and not FORCE_VIEW_PATTERN.search(text)
    ):
        issues.append(
            f"{relative}: same-schema view dependency must use "
            "create or replace force view or explicit controller ordering"
        )

    if directory in ROLLBACK_REQUIRED_DIRS and "--rollback" not in text:
        issues.append(f"{relative}: changeset lacks required rollback annotation")
    return issues


def validate_controllers(root: Path) -> list[str]:
    """Validate the active schema-root controller chain."""
    issues: list[str] = []
    schema_dir = schema_root(root)
    product = product_controller(root)
    if not product.exists():
        return [f"{product.relative_to(root)}: active product controller is missing"]

    controllers = controller_xml_files(root)
    for controller in controllers:
        if not controller.exists():
            issues.append(f"{controller.relative_to(root)}: controller is missing")
            continue
        document = parse_xml(controller)
        if document.findall(".//db:sqlFile", LIQUIBASE_NAMESPACE):
            issues.append(
                f"{controller.relative_to(root)}: active core controller uses sqlFile wrappers"
            )
        try:
            controller.relative_to(schema_dir)
        except ValueError:
            issues.append(
                f"{controller.relative_to(root)}: active core controller is not under "
                "resources/db/schema"
            )
    return issues


def run_checks(root: Path) -> list[str]:
    """Run all core Liquibase checks and return issue lines."""
    resolved_root = root.resolve()
    issues: list[str] = []
    expected = core_schema_sql_files(resolved_root)
    reachable = reachable_sql_files(resolved_root)

    issues.extend(validate_controllers(resolved_root))
    for path in stale_apex_schema_dirs(resolved_root):
        issues.append(
            f"{path.relative_to(resolved_root)}: APEX exports must live under "
            "resources/db/apex, not resources/db/schema"
        )

    for path in sorted(expected):
        issues.extend(validate_sql_file(path, resolved_root))

    for path in sorted(expected - reachable):
        issues.append(
            f"{path.relative_to(resolved_root)}: formatted SQL is not reachable "
            "from resources/db/schema/productController.xml"
        )

    custom_tracking_keys = configured_tracking_table_keys(
        liquibase_core_properties(resolved_root)
    )
    for key in sorted(custom_tracking_keys):
        issues.append(
            f"resources/db/liquibase/liquibase-core.properties: custom {key} "
            "is configured without a documented collision risk"
        )
    return issues


def main(argv: list[str] | None = None) -> int:
    """Run the core Liquibase checker CLI."""
    args = build_parser().parse_args(argv)
    issues = run_checks(args.root)
    for issue in issues:
        print(issue)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
