"""Built-in service manifest for Core knowledge ingestion."""
# Author: Clive Bostock
# Date: 12-Jul-2026
# Description: Declares the Core knowledge worker for the service lifecycle manager.

from __future__ import annotations

import hashlib

from lib.fsutils import project_home
from model.plugin_routing.models import PluginHealthCheck
from model.plugin_routing.models import PluginManifest
from model.plugin_routing.models import PluginServiceRuntime
from model.plugin_routing.models import PluginServiceSchedule


def core_knowledge_service_manifest() -> PluginManifest:
    """Return a synthetic manifest for the Core-owned knowledge worker."""
    src_root = project_home() / "src"
    plugin_dir = src_root / "orac_core"
    manifest_hash = hashlib.sha256(b"orac-core-knowledge-service-v1").hexdigest()
    runtime = PluginServiceRuntime(
        service_code="knowledge_ingestion",
        entry_point="knowledge.worker:KnowledgeIngestionService",
        execution_model="scheduled",
        start_policy="auto",
        restart_policy="on_failure",
        shutdown_timeout_seconds=10,
        health_check=PluginHealthCheck(enabled=True, method="health"),
        schedule=PluginServiceSchedule(
            interval_seconds=30,
            run_on_start=True,
            jitter_seconds=5,
            timeout_seconds=300,
        ),
    )
    return PluginManifest(
        schema_version=1,
        plugin_id="orac_core",
        name="Core Knowledge Ingestion",
        description="Core-owned managed-file knowledge ingestion worker.",
        version="1.0.0",
        enabled=True,
        capabilities=("knowledge.ingest",),
        entitlements=(),
        entities=("knowledge_document",),
        examples=(),
        entry_point=None,
        manifest_path=src_root / "orac_core_knowledge_manifest.json",
        plugin_dir=plugin_dir,
        manifest_hash=manifest_hash,
        runtime_mode="service",
        service_runtime=runtime,
    )
