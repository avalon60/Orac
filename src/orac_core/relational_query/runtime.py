"""Connect Core chat and queued APEX query entrypoints to one service."""

# Author: Clive Bostock
# Date: 08-Nov-2026
# Description: Host-only query composition and lifecycle reconciliation.
# Purpose: Keep plugin code out of SQL generation and execution.
# Usage: QueryRuntime(plugin_manager, config_mgr, connector).query(...).
from __future__ import annotations

from dataclasses import asdict, replace
import json
import socket
import uuid
from typing import Any

from orac_core.communications.models import PrincipalContext
from .catalogue import MetadataCatalogue
from .executor import OracleQueryExecutor, plugin_executor_session
from .models import QueryDenied
from .reviewed import validate_snapshot
from .repository import DatabaseQueryBudget, QueryRepository
from .service import ConnectorGenerator, RelationalQueryService


class QueryRuntime:
    """Resolve datasets from current host-validated installed manifests."""

    def __init__(
        self,
        plugin_manager: Any,
        config_mgr: Any,
        connector: Any,
        repository: QueryRepository | None = None,
    ) -> None:
        """Compose shared Core-owned policy, metadata, generator and executor."""
        self.manager, self.config = plugin_manager, config_mgr
        self.repository = repository or QueryRepository()
        self._fingerprint: tuple = ()
        self._hashes: dict[str, str] = {}
        self._service = RelationalQueryService(
            datasets={},
            eligible=self._eligible,
            metadata=MetadataCatalogue(
                lambda: plugin_executor_session(config_mgr)
            ).load,
            generator=ConnectorGenerator(connector),
            review=self._review,
            executor=OracleQueryExecutor(lambda: plugin_executor_session(config_mgr)),
            audit=self.repository.audit,
            enabled=False,
            budget=DatabaseQueryBudget(self.repository),
        )

    def _review(self, dataset: Any) -> Any:
        """Fetch and validate the current immutable operator review on every boundary."""
        manifest = self.manager.get_manifest(dataset.plugin_id)
        if manifest is None:
            raise QueryDenied("DATASET_UNAVAILABLE")
        return validate_snapshot(
            self.repository.reviewed_metadata(dataset, manifest.manifest_hash),
            dataset,
            manifest.manifest_hash,
        )

    def _eligible(self, principal: PrincipalContext, dataset: Any) -> bool:
        manifest = self.manager.get_manifest(dataset.plugin_id)
        return bool(
            manifest
            and manifest.enabled
            and dataset.capability_id in manifest.capabilities
            and any(
                item.dataset_id == dataset.dataset_id
                for item in manifest.query_datasets
            )
            and self.repository.available(dataset, manifest.manifest_hash)
        )

    def refresh(self) -> None:
        """Reconcile declarations and invalidate metadata on lifecycle changes."""
        # The manager's manifest inventory already reflects installation and
        # readiness; do not scan arbitrary working-tree plugin directories.
        manifests = tuple(getattr(self.manager, "_manifests", {}).values())
        fingerprint = tuple(
            sorted(
                (item.plugin_id, item.manifest_hash, item.enabled) for item in manifests
            )
        )
        enabled = str(
            self.config.config_value("relational_query", "enabled", default="false")
        ).lower() in ("true", "yes", "1")
        self._service.enabled = enabled
        if not enabled or fingerprint == self._fingerprint:
            return
        datasets = {}
        for manifest in manifests:
            for dataset in manifest.query_datasets:
                self.repository.sync(dataset, manifest.manifest_hash)
                # The DB gate is rechecked at every eligibility boundary. The
                # immutable contract is verified only after registration exists.
                datasets[dataset.dataset_id] = replace(dataset, verified=True)
        self._service.datasets = datasets
        self._service.invalidate_metadata()
        self._fingerprint = fingerprint

    def query(
        self,
        principal: PrincipalContext,
        dataset_id: str,
        question: str,
        correlation_id: str,
        restrictions: Any = None,
    ) -> Any:
        """Enter the shared service using only trusted host principal context."""
        self.refresh()
        return self._service.query(
            principal, dataset_id, question, correlation_id, restrictions
        )

    def run_queue(self) -> int:
        """Claim and process one session-bound request using the same service."""
        self.refresh()
        self.repository.purge_expired()
        if not self._service.enabled:
            return 0
        worker = f"{socket.gethostname()}:{uuid.uuid4()}"
        request = self.repository.claim(worker)
        if not request:
            return 0
        try:
            result = self._service.query(
                PrincipalContext(request["username"]),
                request["dataset_id"],
                request["question"],
                str(request["request_id"]),
                queue_request_id=request["request_id"],
            )
            self.repository.complete(
                request, worker, json.dumps(asdict(result), ensure_ascii=False)
            )
        except QueryDenied as exc:
            self.repository.complete(request, worker, None, str(exc))
        return 1
