"""Filesystem cache for plugin routing embeddings."""

# Author: Clive Bostock
# Date: 2026-04-23
# Description: Loads and stores runtime-only plugin embedding cache files.

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
from pathlib import Path


class PluginEmbeddingCache:
    """Persists plugin embedding cache files under a runtime cache directory."""

    CACHE_SCHEMA_VERSION = 1

    def __init__(self, cache_dir: Path, logger=None):
        self._cache_dir = Path(cache_dir)
        self._logger = logger

    @property
    def cache_dir(self) -> Path:
        """Returns the base directory used for cache files."""
        return self._cache_dir

    @classmethod
    def default_cache_dir(cls, project_root: Path) -> Path:
        """Returns the default runtime cache location for plugin routing."""
        override = os.environ.get("ORAC_PLUGIN_ROUTER_CACHE_DIR")
        if override:
            return Path(override).expanduser()
        return Path(project_root) / "var" / "cache" / "plugin_router"

    def load(
        self, embedding_model_id: str, intent_text_version: str
    ) -> dict[str, dict]:
        """Loads cache entries valid for the given embedding model and intent version."""
        cache_path = self._cache_path(embedding_model_id)
        if not cache_path.exists():
            self._log_debug(f"Plugin routing cache miss: {cache_path}")
            return {}

        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except OSError as exc:
            self._log_warning(
                f"Plugin routing cache read failed at {cache_path}: {exc}"
            )
            return {}
        except json.JSONDecodeError as exc:
            self._log_warning(
                f"Plugin routing cache is invalid JSON at {cache_path}: {exc}"
            )
            return {}

        if payload.get("cache_schema_version") != self.CACHE_SCHEMA_VERSION:
            self._log_warning(
                f"Plugin routing cache schema mismatch at {cache_path}; ignoring cache."
            )
            return {}
        if payload.get("embedding_model_id") != embedding_model_id:
            self._log_warning(
                f"Plugin routing cache model mismatch at {cache_path}; ignoring cache."
            )
            return {}
        if payload.get("intent_text_version") != intent_text_version:
            self._log_warning(
                f"Plugin routing cache intent-text version mismatch at {cache_path}; ignoring cache."
            )
            return {}

        plugins = payload.get("plugins")
        if not isinstance(plugins, dict):
            self._log_warning(
                f"Plugin routing cache payload is malformed at {cache_path}; ignoring cache."
            )
            return {}

        valid_entries: dict[str, dict] = {}
        for plugin_id, entry in plugins.items():
            if self._is_valid_entry(plugin_id, entry):
                valid_entries[plugin_id] = entry
        self._log_debug(
            f"Plugin routing cache loaded from {cache_path} with {len(valid_entries)} valid entries."
        )
        return valid_entries

    def save(
        self,
        embedding_model_id: str,
        intent_text_version: str,
        plugin_entries: dict[str, dict],
    ) -> Path:
        """Writes cache entries atomically to disk."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self._cache_path(embedding_model_id)
        temp_path = cache_path.with_suffix(".tmp")
        payload = {
            "cache_schema_version": self.CACHE_SCHEMA_VERSION,
            "embedding_model_id": embedding_model_id,
            "intent_text_version": intent_text_version,
            "plugins": plugin_entries,
        }
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temp_path.replace(cache_path)
        self._log_debug(
            f"Plugin routing cache saved to {cache_path} with {len(plugin_entries)} entries."
        )
        return cache_path

    def remove_plugin(
        self,
        plugin_id: str,
        *,
        expected_device: int | None,
        expected_inode: int | None,
        dry_run: bool = False,
    ) -> None:
        """Remove one plugin's derived routes while preserving shared cache entries.

        The caller holds exclusive host maintenance access. Replacement is
        atomic and no symlink, unexpected cache shape or replaced root is used.
        """
        root = self._cache_dir.absolute()
        if ".." in root.parts or not re.fullmatch(r"[a-z][a-z0-9_]*", plugin_id):
            raise ValueError("Invalid plugin cache cleanup target.")
        descriptor = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY)
        try:
            for part in root.parts[1:]:
                try:
                    child = os.open(
                        part,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=descriptor,
                    )
                except FileNotFoundError:
                    return
                os.close(descriptor)
                descriptor = child
            info = os.fstat(descriptor)
            if (info.st_dev, info.st_ino) != (expected_device, expected_inode):
                raise ValueError("Plugin cache directory changed after authorization.")
            for name in os.listdir(descriptor):
                if not name.endswith(".json"):
                    continue
                source = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=descriptor)
                with os.fdopen(source, "r", encoding="utf-8") as stream:
                    original = os.fstat(stream.fileno())
                    if (
                        not stat.S_ISREG(original.st_mode)
                        or original.st_size > 100 * 1024 * 1024
                    ):
                        raise ValueError("Plugin cache must be a bounded regular file.")
                    payload = json.load(stream)
                if (
                    not isinstance(payload, dict)
                    or payload.get("cache_schema_version") != self.CACHE_SCHEMA_VERSION
                    or not isinstance(payload.get("embedding_model_id"), str)
                    or not isinstance(payload.get("plugins"), dict)
                    or self._cache_path(payload["embedding_model_id"]).name != name
                ):
                    raise ValueError("Unrecognized plugin cache file blocks cleanup.")
                entries = payload["plugins"]
                keys = [
                    key
                    for key, entry in entries.items()
                    if key == plugin_id
                    or isinstance(entry, dict)
                    and entry.get("plugin_id") == plugin_id
                ]
                if not keys or dry_run:
                    continue
                for key in keys:
                    del entries[key]
                temporary = ".removal-" + uuid.uuid4().hex + ".tmp"
                try:
                    target = os.open(
                        temporary,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=descriptor,
                    )
                    with os.fdopen(target, "w", encoding="utf-8") as stream:
                        json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
                        stream.flush()
                        os.fsync(stream.fileno())
                    current = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                    if (current.st_dev, current.st_ino) != (
                        original.st_dev,
                        original.st_ino,
                    ):
                        raise ValueError("Plugin cache file changed during cleanup.")
                    os.replace(
                        temporary, name, src_dir_fd=descriptor, dst_dir_fd=descriptor
                    )
                    os.fsync(descriptor)
                finally:
                    try:
                        os.unlink(temporary, dir_fd=descriptor)
                    except FileNotFoundError:
                        pass
        finally:
            os.close(descriptor)

    def _cache_path(self, embedding_model_id: str) -> Path:
        safe_model_id = self._safe_model_token(embedding_model_id)
        return self._cache_dir / f"{safe_model_id}.json"

    @staticmethod
    def _safe_model_token(embedding_model_id: str) -> str:
        """Returns a filesystem-safe token derived from the embedding model id."""
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", embedding_model_id.strip()).strip(
            "._-"
        )
        digest = hashlib.sha256(embedding_model_id.encode("utf-8")).hexdigest()[:12]
        if cleaned:
            return f"{cleaned[:40]}-{digest}"
        return digest

    @staticmethod
    def _is_valid_entry(plugin_id: str, entry: object) -> bool:
        if not isinstance(entry, dict):
            return False
        route_key = str(entry.get("route_key") or entry.get("plugin_id") or "")
        if route_key != plugin_id:
            return False
        if not isinstance(entry.get("plugin_id"), str):
            return False
        if not isinstance(entry.get("manifest_hash"), str):
            return False
        if not isinstance(entry.get("canonical_text"), str):
            return False
        vector = entry.get("vector")
        if not isinstance(vector, list) or not vector:
            return False
        return all(isinstance(value, (int, float)) for value in vector)

    def _log_debug(self, message: str) -> None:
        if self._logger is not None:
            self._logger.log_debug(message)

    def _log_warning(self, message: str) -> None:
        if self._logger is not None:
            self._logger.log_warning(message)
