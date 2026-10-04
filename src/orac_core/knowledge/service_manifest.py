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


def core_knowledge_service_manifest(
    *,
    include_knowledge: bool = True,
    include_conversation_memory: bool = False,
    include_conversation_title: bool = True,
) -> PluginManifest:
    """Return a synthetic manifest for enabled Core-owned workers."""
    src_root = project_home() / "src"
    plugin_dir = src_root / "orac_core"
    manifest_hash = hashlib.sha256(
        (
            "orac-core-services-v3:"
            f"knowledge={include_knowledge}:memory={include_conversation_memory}"
            f":title={include_conversation_title}"
        ).encode("utf-8")
    ).hexdigest()
    knowledge_runtime = PluginServiceRuntime(
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
    memory_runtime = PluginServiceRuntime(
        service_code="conversation_memory",
        entry_point=(
            "conversation_memory.worker:"
            "ConversationMemoryMaterialisationService"
        ),
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
    title_runtime = PluginServiceRuntime(
        service_code="conversation_title",
        entry_point="conversation_title.worker:ConversationTitleService",
        execution_model="scheduled",
        start_policy="auto",
        restart_policy="on_failure",
        shutdown_timeout_seconds=10,
        health_check=PluginHealthCheck(enabled=True, method="health"),
        schedule=PluginServiceSchedule(
            interval_seconds=5,
            run_on_start=True,
            jitter_seconds=1,
            timeout_seconds=60,
        ),
    )
    runtimes = tuple(
        runtime
        for enabled, runtime in (
            (include_knowledge, knowledge_runtime),
            (include_conversation_memory, memory_runtime),
            (include_conversation_title, title_runtime),
        )
        if enabled
    )
    if not runtimes:
        raise ValueError("At least one Core service runtime must be enabled.")
    return PluginManifest(
        schema_version=1,
        plugin_id="orac_core",
        name="Core Background Services",
        description="Core-owned knowledge and conversation-memory workers.",
        version="1.0.0",
        enabled=True,
        capabilities=tuple(
            capability
            for enabled, capability in (
                (include_knowledge, "knowledge.ingest"),
                (include_conversation_memory, "conversation_memory.materialise"),
                (include_conversation_title, "conversation.title"),
            )
            if enabled
        ),
        entitlements=(),
        entities=("knowledge_document",),
        examples=(),
        entry_point=None,
        manifest_path=src_root / "orac_core_knowledge_manifest.json",
        plugin_dir=plugin_dir,
        manifest_hash=manifest_hash,
        runtime_mode="service",
        service_runtime=runtimes[0],
        service_runtimes=runtimes,
    )
