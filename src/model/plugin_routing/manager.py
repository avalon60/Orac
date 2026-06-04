"""Facade for plugin discovery, embedding cache refresh, and candidate search."""
# Author: Clive Bostock
# Date: 2026-04-23
# Description: Coordinates manifest scanning, cache reuse, in-memory indexing, and candidate lookup.

from __future__ import annotations

from pathlib import Path
from typing import Any

from lib.fsutils import project_home
from model.plugin_config import PluginConfigManager
from model.plugin_config import PluginConfigurationResult
from model.plugin_database_deployment import PluginDatabaseDeployer
from model.plugin_database_deployment import PluginDatabaseDeploymentResult
from model.plugin_routing.cache import PluginEmbeddingCache
from model.plugin_routing.discovery import PluginDiscovery
from model.plugin_routing.embeddings import EmbeddingProvider
from model.plugin_routing.index import PluginIntentIndex
from model.plugin_routing.intent_text import INTENT_TEXT_VERSION, build_canonical_intent_text
from model.plugin_routing.models import PluginCandidate, PluginManifest


class PluginManager:
    """Coordinates plugin routing state without importing plugin code."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        plugins_dir: Path | None = None,
        cache_dir: Path | None = None,
        logger=None,
        database_schema_root: Path | None = None,
        database_deployer: PluginDatabaseDeployer | None = None,
    ):
        self._project_root = project_home()
        self._plugins_dir = Path(plugins_dir) if plugins_dir else self._project_root / "plugins"
        self._database_schema_root = (
            Path(database_schema_root)
            if database_schema_root
            else self._project_root / "resources" / "db" / "schema"
        )
        self._database_deployer = database_deployer or PluginDatabaseDeployer(
            logger=logger
        )
        self._cache = PluginEmbeddingCache(
            cache_dir or PluginEmbeddingCache.default_cache_dir(self._project_root),
            logger=logger,
        )
        self._embedding_provider = embedding_provider
        self._discovery = PluginDiscovery(self._plugins_dir)
        self._index = PluginIntentIndex()
        self._manifests: dict[str, PluginManifest] = {}
        self._discovered_manifests: tuple[PluginManifest, ...] = ()
        self._deployment_eligible_manifests: tuple[PluginManifest, ...] = ()
        self._configuration_results: dict[str, PluginConfigurationResult] = {}
        self._deployment_results: dict[str, PluginDatabaseDeploymentResult] = {}
        self._last_refresh_report: dict[str, Any] = {}
        self._logger = logger

    def refresh(self) -> dict[str, Any]:
        """Refreshes manifests, cache, embeddings, and the in-memory index."""
        self._log_info(f"Plugin routing refresh starting for root {self._plugins_dir}")
        discovered_count = len(list(self._plugins_dir.glob("*.json"))) if self._plugins_dir.exists() else 0
        manifests, errors = self._discovery.discover()
        self._discovered_manifests = tuple(manifests)
        valid_count = len(manifests)
        invalid_count = len(errors)
        enabled_manifests = [manifest for manifest in manifests if manifest.enabled]
        disabled_count = valid_count - len(enabled_manifests)
        configuration_eligible_manifests, configuration_disabled_manifests = (
            self._configuration_eligible_manifests_for(enabled_manifests)
        )
        deployment_eligible_manifests, deployment_disabled_manifests = self._deployment_eligible_manifests_for(
            configuration_eligible_manifests
        )
        self._deployment_eligible_manifests = tuple(deployment_eligible_manifests)
        runtime_manifests, runtime_disabled_manifests = self._runtime_eligible_manifests(
            deployment_eligible_manifests
        )
        dependency_disabled_manifests = [
            *configuration_disabled_manifests,
            *deployment_disabled_manifests,
            *runtime_disabled_manifests,
        ]
        for error in errors:
            self._log_warning(f"Plugin routing invalid manifest skipped: {error}")
        if disabled_count:
            self._log_info(f"Plugin routing skipped {disabled_count} disabled plugin manifest(s).")

        cached_entries = self._cache.load(
            embedding_model_id=self._embedding_provider.model_id,
            intent_text_version=INTENT_TEXT_VERSION,
        )

        vectors_for_index: dict[str, list[float]] = {}
        cache_entries_to_save: dict[str, dict] = {}
        cache_hits = 0
        cache_misses = 0
        re_embedded = 0

        for manifest in runtime_manifests:
            canonical_text = build_canonical_intent_text(manifest)
            cached_entry = cached_entries.get(manifest.plugin_id)

            if self._is_cache_hit(manifest, canonical_text, cached_entry):
                vector = [float(value) for value in cached_entry["vector"]]
                cache_hits += 1
            else:
                if cached_entry is None:
                    cache_misses += 1
                else:
                    self._log_debug(
                        f"Plugin routing cache entry stale for plugin '{manifest.plugin_id}'; re-embedding."
                    )
                try:
                    vector = self._embedding_provider.embed_text(canonical_text)
                except Exception as exc:
                    self._log_error(
                        f"Plugin routing embedding failed for plugin '{manifest.plugin_id}': {exc}"
                    )
                    raise
                re_embedded += 1

            vectors_for_index[manifest.plugin_id] = vector
            cache_entries_to_save[manifest.plugin_id] = {
                "plugin_id": manifest.plugin_id,
                "manifest_hash": manifest.manifest_hash,
                "canonical_text": canonical_text,
                "vector": vector,
            }

        self._cache.save(
            embedding_model_id=self._embedding_provider.model_id,
            intent_text_version=INTENT_TEXT_VERSION,
            plugin_entries=cache_entries_to_save,
        )

        self._index.build(vectors_for_index)
        self._manifests = {manifest.plugin_id: manifest for manifest in runtime_manifests}
        self._last_refresh_report = {
            "plugin_root": str(self._plugins_dir),
            "cache_dir": str(self._cache.cache_dir),
            "discovered": discovered_count,
            "valid": valid_count,
            "invalid": invalid_count,
            "enabled": len(enabled_manifests),
            "disabled": disabled_count,
            "dependency_disabled": len(dependency_disabled_manifests),
            "configuration_status": {
                plugin_id: result.status
                for plugin_id, result in sorted(self._configuration_results.items())
            },
            "deployment_status": {
                plugin_id: result.status
                for plugin_id, result in sorted(self._deployment_results.items())
            },
            "indexed_plugin_count": self._index.size(),
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "re_embedded": re_embedded,
            "validation_errors": errors,
            "embedding_model_id": self._embedding_provider.model_id,
            "intent_text_version": INTENT_TEXT_VERSION,
        }
        self._log_info(
            "Plugin routing refresh complete: "
            f"discovered={discovered_count} valid={valid_count} invalid={invalid_count} "
            f"enabled={len(enabled_manifests)} disabled={disabled_count} "
            f"dependency_disabled={len(dependency_disabled_manifests)} "
            f"cache_hits={cache_hits} cache_misses={cache_misses} re_embedded={re_embedded}"
        )
        return dict(self._last_refresh_report)

    def find_candidates(
        self,
        utterance: str,
        top_n: int = 5,
        min_score: float | None = None,
    ) -> list[PluginCandidate]:
        """Returns scored plugin candidates for a user utterance."""
        if not self._manifests:
            self.refresh()

        query_vector = self._embedding_provider.embed_text(utterance)
        return self._index.search(query_vector=query_vector, top_n=top_n, min_score=min_score)

    def get_manifest(self, plugin_id: str) -> PluginManifest | None:
        """Returns the manifest for an indexed plugin."""
        return self._manifests.get(plugin_id)

    def discovered_manifests(self) -> tuple[PluginManifest, ...]:
        """Returns all valid manifests found during the last refresh."""
        return self._discovered_manifests

    def deployment_eligible_manifests(self) -> tuple[PluginManifest, ...]:
        """Return enabled manifests that passed required database deployment checks."""
        return self._deployment_eligible_manifests

    def status(self) -> dict[str, Any]:
        """Returns the last refresh report."""
        return dict(self._last_refresh_report)

    @staticmethod
    def _is_cache_hit(
        manifest: PluginManifest,
        canonical_text: str,
        cached_entry: dict[str, Any] | None,
    ) -> bool:
        if not cached_entry:
            return False
        return (
            cached_entry.get("manifest_hash") == manifest.manifest_hash
            and cached_entry.get("canonical_text") == canonical_text
        )

    def _runtime_eligible_manifests(
        self,
        manifests: list[PluginManifest],
    ) -> tuple[list[PluginManifest], list[PluginManifest]]:
        """Return manifests eligible for on-demand routing and dependency-disabled manifests."""
        eligible: list[PluginManifest] = []
        dependency_disabled: list[PluginManifest] = []

        for manifest in manifests:
            if manifest.runtime_mode == "service":
                continue
            eligible.append(manifest)

        return eligible, dependency_disabled

    def _configuration_eligible_manifests_for(
        self,
        manifests: list[PluginManifest],
    ) -> tuple[list[PluginManifest], list[PluginManifest]]:
        """Return enabled manifests whose plugin-local configuration is usable."""
        eligible: list[PluginManifest] = []
        dependency_disabled: list[PluginManifest] = []
        self._configuration_results = {}

        for manifest in manifests:
            manager = PluginConfigManager(manifest, logger=self._logger)
            result = manager.validate()
            self._configuration_results[manifest.plugin_id] = result
            if result.eligible:
                eligible.append(manifest)
                continue

            dependency_disabled.append(manifest)
            detail_keys = result.missing_keys or result.uninitialised_keys
            detail_text = ", ".join(detail_keys) if detail_keys else "unknown"
            self._log_warning(
                "Plugin routing skipped enabled plugin "
                f"'{manifest.plugin_id}' because plugin configuration status is "
                f"{result.status}: {result.message} Affected key(s): {detail_text}"
            )

        return eligible, dependency_disabled

    def _deployment_eligible_manifests_for(
        self,
        manifests: list[PluginManifest],
    ) -> tuple[list[PluginManifest], list[PluginManifest]]:
        """Return enabled manifests whose required plugin database payload is available."""
        eligible: list[PluginManifest] = []
        dependency_disabled: list[PluginManifest] = []
        self._deployment_results = {}

        for manifest in manifests:
            result = self._database_deployer.deploy_if_needed(manifest)
            self._deployment_results[manifest.plugin_id] = result
            if result.eligible:
                eligible.append(manifest)
                if result.status in {"deployed", "already_deployed"}:
                    self._log_info(
                        "Plugin database deployment status for "
                        f"'{manifest.plugin_id}': {result.status}. {result.message}"
                    )
                continue

            if manifest.database_on_missing == "fail_refresh":
                raise RuntimeError(
                    "Plugin routing refresh failed because plugin "
                    f"'{manifest.plugin_id}' database deployment failed: {result.message}"
                )

            dependency_disabled.append(manifest)
            self._log_warning(
                "Plugin routing skipped enabled plugin "
                f"'{manifest.plugin_id}' because required database deployment "
                f"status is {result.status}: {result.message}"
            )

        return eligible, dependency_disabled

    def _has_missing_database_schema(self, manifest: PluginManifest) -> bool:
        """Return whether a manifest declares a required schema with no local bundle."""
        for schema in manifest.database_schemas:
            if not (self._database_schema_root / schema.schema_name).is_dir():
                return True
        return False

    def _log_debug(self, message: str) -> None:
        if self._logger is not None:
            self._logger.log_debug(message)

    def _log_info(self, message: str) -> None:
        if self._logger is not None:
            self._logger.log_info(message)

    def _log_warning(self, message: str) -> None:
        if self._logger is not None:
            self._logger.log_warning(message)

    def _log_error(self, message: str) -> None:
        if self._logger is not None:
            self._logger.log_error(message)
