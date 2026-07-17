"""Tests for bundled plugin Bump2Version configuration."""

# Author: Clive Bostock
# Date: 17-Jul-2026
# Description: Verifies plugin release bump configuration and scoped targets.

from __future__ import annotations

import configparser
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from model.plugin_routing.discovery import PluginDiscovery  # noqa: E402


EXPECTED_BUMP_TARGETS = {
    "drop_box": {"../drop_box.json"},
    "home_assistant": {"../home_assistant.json", "manifest.ini"},
    "media_control": {"../media_control.json"},
    "weather": {"../weather.json"},
}


class PluginBumpVersionConfigTests(unittest.TestCase):
    """Verify each bundled plugin has an accurate local bump config."""

    def test_every_bundled_plugin_has_manifest_aligned_config(self) -> None:
        manifests, errors = PluginDiscovery(PROJECT_ROOT / "plugins").discover()

        self.assertEqual(errors, [])
        self.assertEqual(
            {manifest.plugin_id for manifest in manifests},
            set(EXPECTED_BUMP_TARGETS),
        )
        for manifest in manifests:
            with self.subTest(plugin_id=manifest.plugin_id):
                config_path = manifest.plugin_dir / ".bumpversion.cfg"
                config = _read_config(config_path)

                self.assertEqual(
                    config.get("bumpversion", "current_version"),
                    manifest.version,
                )
                self.assertEqual(config.getboolean("bumpversion", "commit"), False)
                self.assertEqual(config.getboolean("bumpversion", "tag"), False)
                self.assertEqual(
                    _configured_targets(config),
                    EXPECTED_BUMP_TARGETS[manifest.plugin_id],
                )
                self.assertIn(
                    f"../{manifest.plugin_id}.json",
                    _configured_targets(config),
                )
                self.assertEqual(
                    json.loads(manifest.manifest_path.read_text(encoding="utf-8"))[
                        "version"
                    ],
                    manifest.version,
                )

    def test_configured_search_patterns_exist_in_target_files(self) -> None:
        for plugin_id, targets in EXPECTED_BUMP_TARGETS.items():
            config_path = PROJECT_ROOT / "plugins" / plugin_id / ".bumpversion.cfg"
            config = _read_config(config_path)
            current_version = config.get("bumpversion", "current_version")

            for target in targets:
                with self.subTest(plugin_id=plugin_id, target=target):
                    section = f"bumpversion:file:{target}"
                    target_path = (config_path.parent / target).resolve()
                    search = config.get(section, "search").replace(
                        "{current_version}",
                        current_version,
                    )

                    self.assertTrue(target_path.is_file())
                    self.assertIn(search, target_path.read_text(encoding="utf-8"))

    def test_controlled_bump_updates_all_configured_home_assistant_targets(self) -> None:
        executable = shutil.which("bump2version")
        if executable is None:
            self.skipTest("bump2version executable is not available")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plugin_dir = root / "home_assistant"
            plugin_dir.mkdir()
            shutil.copy2(
                PROJECT_ROOT / "plugins" / "home_assistant.json",
                root / "home_assistant.json",
            )
            shutil.copy2(
                PROJECT_ROOT / "plugins" / "home_assistant" / ".bumpversion.cfg",
                plugin_dir / ".bumpversion.cfg",
            )
            shutil.copy2(
                PROJECT_ROOT / "plugins" / "home_assistant" / "manifest.ini",
                plugin_dir / "manifest.ini",
            )

            result = subprocess.run(
                [executable, "--allow-dirty", "patch"],
                cwd=plugin_dir,
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads(
                (root / "home_assistant.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["version"], "1.0.3")
            self.assertIn(
                "version = 1.0.3",
                (plugin_dir / "manifest.ini").read_text(encoding="utf-8"),
            )


def _read_config(path: Path) -> configparser.RawConfigParser:
    """Read a Bump2Version config without interpolation side effects."""
    config = configparser.RawConfigParser()
    self_read = config.read(path, encoding="utf-8")
    if not self_read:
        raise AssertionError(f"Unable to read config: {path}")
    return config


def _configured_targets(config: configparser.RawConfigParser) -> set[str]:
    """Return configured Bump2Version file targets."""
    prefix = "bumpversion:file:"
    return {
        section[len(prefix) :]
        for section in config.sections()
        if section.startswith(prefix)
    }
