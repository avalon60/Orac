#!/usr/bin/env python3
"""Inspect, reconcile, and migrate Core knowledge managed storage."""

# Author: Clive Bostock
# Date: 07-Sep-2026
# Description: Runs knowledge inspection, reprocessing, and migration operations.
# Codex-assisted generated/modified.
# Codex SDK reviewability guardrails followed.

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from loguru import logger
import oracledb

from lib.config_mgr import ConfigManager
from lib.fsutils import project_home
from orac_core.knowledge.maintenance import DEFAULT_SCAN_LIMIT
from orac_core.knowledge.maintenance import KnowledgeMigrationRepository
from orac_core.knowledge.maintenance import KnowledgeMigrationService
from orac_core.knowledge.managed_store import KnowledgeManagedStore
from orac_core.knowledge.managed_store import ManagedStoreError
from orac_core.knowledge.reconciliation import DEFAULT_MAX_DATABASE_ROWS
from orac_core.knowledge.reconciliation import DEFAULT_MAX_ELAPSED_SECONDS
from orac_core.knowledge.reconciliation import DEFAULT_MAX_FILESYSTEM_ENTRIES
from orac_core.knowledge.reconciliation import DEFAULT_MAX_HASHED_BYTES
from orac_core.knowledge.reconciliation import DEFAULT_MAX_REPORT_BYTES
from orac_core.knowledge.reconciliation import DEFAULT_MAX_REPORT_ITEMS_PER_REASON
from orac_core.knowledge.reconciliation import (
    DEFAULT_MAX_TEMPORARY_FILES_HASHED,
)
from orac_core.knowledge.reconciliation import (
    DEFAULT_STALE_TEMPORARY_AGE_SECONDS,
)
from orac_core.knowledge.reconciliation import (
    DEFAULT_UNREGISTERED_OBJECT_GRACE_SECONDS,
)
from orac_core.knowledge.reconciliation import KnowledgeReconciliationRepository
from orac_core.knowledge.reconciliation import KnowledgeReconciliationService
from orac_core.knowledge.reconciliation import ReconciliationLimits
from orac_core.knowledge.embeddings import knowledge_embedding_provider
from orac_core.knowledge.reembedding import KnowledgeReembeddingService
from orac_core.knowledge.repository import KnowledgeEmbeddingRepository
from orac_core.knowledge.repository import KnowledgeIngestionRepository

DEFAULT_APPLY_LIMIT = 25


def build_parser() -> argparse.ArgumentParser:
    """Build the knowledge maintenance command parser."""
    parser = argparse.ArgumentParser(
        prog="orac-knowledge",
        description="Inspect and migrate legacy Core knowledge storage.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    preflight = subparsers.add_parser(
        "preflight",
        help="Run the strictly read-only migration preflight.",
    )
    _add_report_options(preflight, include_limit=False)
    reconcile = subparsers.add_parser(
        "reconcile",
        help="Run bounded read-only database and managed-store reconciliation.",
    )
    _add_reconciliation_options(reconcile)
    for command, help_text in (
        ("backfill", "Backfill legacy extraction CLOBs as PRIMARY artefacts."),
        ("migrate-raw-locators", "Migrate verified legacy shard locators."),
    ):
        operation = subparsers.add_parser(command, help=help_text)
        _add_report_options(operation, include_limit=True)
        operation.add_argument(
            "--apply",
            action="store_true",
            help="Apply the bounded batch; without this flag the command is read-only.",
        )
    reembed = subparsers.add_parser(
        "reembed",
        help="Build native semantic embeddings from existing normalized chunks.",
    )
    reembed.add_argument("--run-id", type=int, default=None)
    reembed.add_argument("--batch-size", type=int, default=16)
    reembed.add_argument("--max-batches", type=int, default=1000)
    reembed.add_argument(
        "--activate",
        action="store_true",
        help="Atomically activate the profile after complete validation.",
    )
    reembed.add_argument("--json", action="store_true")
    activate_profile = subparsers.add_parser(
        "activate-profile",
        help="Atomically activate a complete, current native profile for rollback.",
    )
    activate_profile.add_argument("embedding_profile_id", type=int)
    activate_profile.add_argument("--json", action="store_true")
    retry_ingestion = subparsers.add_parser(
        "retry-ingestion",
        help="Requeue one failed ingestion request without recapturing its source.",
    )
    retry_ingestion.add_argument("ingestion_request_id", type=int)
    retry_ingestion.add_argument("--json", action="store_true")
    return parser


def _add_reconciliation_options(parser: argparse.ArgumentParser) -> None:
    """Add lower-only reconciliation safety overrides."""
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the stable knowledge-reconciliation JSON report.",
    )
    for option, help_text in (
        ("max-database-rows", "database rows across both snapshots"),
        ("max-filesystem-entries", "filesystem entries enumerated"),
        ("max-hashed-bytes", "managed-store bytes hashed"),
        ("max-temporary-files-hashed", "temporary files hashed"),
        ("max-elapsed-seconds", "elapsed scan seconds"),
        ("max-report-items-per-reason", "numeric samples retained per reason"),
        ("max-report-bytes", "serialized report bytes"),
    ):
        parser.add_argument(
            f"--{option}",
            type=int,
            default=None,
            help=f"Lower the configured ceiling for {help_text}.",
        )


def _add_report_options(
    parser: argparse.ArgumentParser,
    *,
    include_limit: bool,
) -> None:
    """Add common bounded report arguments."""
    parser.add_argument(
        "--scan-limit",
        type=int,
        default=DEFAULT_SCAN_LIMIT,
        help=f"Maximum rows per candidate class to inspect (default: {DEFAULT_SCAN_LIMIT}).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the stable version-one JSON report.",
    )
    if include_limit:
        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_APPLY_LIMIT,
            help=f"Maximum items to apply (default: {DEFAULT_APPLY_LIMIT}).",
        )


def _config() -> ConfigManager:
    """Load the canonical repository configuration."""
    return ConfigManager(
        config_file_path=project_home() / "resources" / "config" / "orac.ini"
    )


def _inspection_store(config: ConfigManager) -> KnowledgeManagedStore:
    """Open the configured store without changing filesystem state."""
    root = config.path_config_value(
        "knowledge",
        "managed_root",
        suppress_warnings=True,
    )
    return KnowledgeManagedStore.for_read_only_inspection(
        Path(root),
        configuration_source="[knowledge].managed_root",
    )


def _service(
    config: ConfigManager,
    *,
    write_store: KnowledgeManagedStore | None = None,
) -> KnowledgeMigrationService:
    """Build the maintenance service around runtime-owned boundaries."""
    return KnowledgeMigrationService(
        repository=KnowledgeMigrationRepository(),
        inspection_store=_inspection_store(config),
        write_store=write_store,
    )


def _reconciliation_limits(
    config: ConfigManager,
    args: argparse.Namespace,
) -> ReconciliationLimits:
    """Load configured limits and apply only lower CLI ceilings."""
    section = "knowledge.reconciliation"
    configured = {
        "max_database_rows": config.int_config_value(
            section, "max_database_rows", default=DEFAULT_MAX_DATABASE_ROWS
        ),
        "max_filesystem_entries": config.int_config_value(
            section,
            "max_filesystem_entries",
            default=DEFAULT_MAX_FILESYSTEM_ENTRIES,
        ),
        "max_hashed_bytes": config.int_config_value(
            section, "max_hashed_bytes", default=DEFAULT_MAX_HASHED_BYTES
        ),
        "max_temporary_files_hashed": config.int_config_value(
            section,
            "max_temporary_files_hashed",
            default=DEFAULT_MAX_TEMPORARY_FILES_HASHED,
        ),
        "max_elapsed_seconds": config.int_config_value(
            section, "max_elapsed_seconds", default=DEFAULT_MAX_ELAPSED_SECONDS
        ),
        "max_report_items_per_reason": config.int_config_value(
            section,
            "max_report_items_per_reason",
            default=DEFAULT_MAX_REPORT_ITEMS_PER_REASON,
        ),
        "max_report_bytes": config.int_config_value(
            section, "max_report_bytes", default=DEFAULT_MAX_REPORT_BYTES
        ),
    }
    for name, configured_value in tuple(configured.items()):
        override = getattr(args, name)
        if override is None:
            continue
        if override > configured_value:
            option_name = name.replace("_", "-")
            raise ValueError(
                f"--{option_name} may lower but not raise the configured ceiling."
            )
        configured[name] = override
    return ReconciliationLimits(
        **configured,
        stale_temporary_age_seconds=config.int_config_value(
            section,
            "stale_temporary_age_seconds",
            default=DEFAULT_STALE_TEMPORARY_AGE_SECONDS,
        ),
        unregistered_object_grace_seconds=config.int_config_value(
            section,
            "unregistered_object_grace_seconds",
            default=DEFAULT_UNREGISTERED_OBJECT_GRACE_SECONDS,
        ),
        concurrency=config.int_config_value(section, "concurrency", default=1),
    )


def _reconciliation_service(
    config: ConfigManager,
    args: argparse.Namespace,
) -> KnowledgeReconciliationService:
    """Build the strictly read-only reconciliation service."""
    return KnowledgeReconciliationService(
        repository=KnowledgeReconciliationRepository(),
        inspection_store=_inspection_store(config),
        limits=_reconciliation_limits(config, args),
        configured_root_probe=lambda: _config().path_config_value(
            "knowledge",
            "managed_root",
            suppress_warnings=True,
        ),
    )


def _emit(report: dict[str, object], *, as_json: bool) -> None:
    """Emit one deterministic operator report without sensitive paths."""
    payload = json.dumps(report, indent=2, sort_keys=True, default=str)
    if as_json:
        sys.stdout.write(payload + "\n")
    else:
        logger.info("Knowledge maintenance report:\n{}", payload)


def main(argv: list[str] | None = None) -> int:
    """Run one knowledge maintenance command."""
    args = build_parser().parse_args(argv)
    try:
        config = _config()
        if args.command == "activate-profile":
            repository = KnowledgeEmbeddingRepository()
            repository.activate_profile(args.embedding_profile_id)
            report = {
                "schema_version": 1,
                "operation": "activate_native_knowledge_profile",
                "embedding_profile_id": args.embedding_profile_id,
                "status": "ACTIVE",
            }
        elif args.command == "retry-ingestion":
            KnowledgeIngestionRepository().requeue_failed_request(
                args.ingestion_request_id
            )
            report = {
                "schema_version": 1,
                "operation": "retry_knowledge_ingestion",
                "ingestion_request_id": args.ingestion_request_id,
                "status": "QUEUED",
            }
        elif args.command == "reembed":
            result = KnowledgeReembeddingService(
                repository=KnowledgeEmbeddingRepository(),
                embedding_provider=knowledge_embedding_provider(config),
            ).run(
                reembedding_run_id=args.run_id,
                batch_size=args.batch_size,
                max_batches=args.max_batches,
                activate=args.activate,
            )
            report = {
                "schema_version": 1,
                "operation": "native_knowledge_reembedding",
                "reembedding_run_id": result.reembedding_run_id,
                "embedding_profile_id": result.embedding_profile_id,
                "batches_processed": result.batches_processed,
                "chunks_processed": result.chunks_processed,
                "status": result.status,
            }
        elif args.command == "reconcile":
            report = _reconciliation_service(config, args).reconcile().as_dict()
        else:
            service = _service(config)
        if args.command == "preflight":
            report = service.preflight(scan_limit=args.scan_limit).as_dict()
        elif args.command not in {
            "reconcile",
            "reembed",
            "activate-profile",
            "retry-ingestion",
        }:
            preliminary = service.preflight(scan_limit=args.scan_limit)
            candidates = (
                preliminary.backfill
                if args.command == "backfill"
                else preliminary.raw_locators
            )
            relevant_blockers = any(item.status == "BLOCKED" for item in candidates)
            if args.apply and not relevant_blockers and not preliminary.truncated:
                write_store = (
                    KnowledgeManagedStore.from_config(config)
                    if args.command == "backfill"
                    else None
                )
                service = _service(config, write_store=write_store)
            if args.command == "backfill":
                report = service.backfill(
                    apply=args.apply,
                    limit=args.limit,
                    scan_limit=args.scan_limit,
                )
            else:
                report = service.migrate_raw_locators(
                    apply=args.apply,
                    limit=args.limit,
                    scan_limit=args.scan_limit,
                )
        _emit(report, as_json=args.json)
    except (
        KeyError,
        ManagedStoreError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        oracledb.Error,
    ) as exc:
        if args.command == "reconcile":
            reason_code = getattr(exc, "reason_code", "RECON_OPERATION_FAILED")
            logger.error("Knowledge reconciliation failed: {}", reason_code)
        else:
            logger.error("Knowledge maintenance failed: {}", exc)
        return 1
    status = str(report.get("status") or "")
    if status == "FAILED":
        return 1
    if status == "BLOCKED":
        return 2
    if status == "INCOMPLETE":
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
