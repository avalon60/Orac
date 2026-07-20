"""Tests for shared plugin dialogue interception."""
# Author: Clive Bostock
# Date: 17-Jul-2026
# Description: Verifies route-id based interception and immutable route evidence.

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
for path in (SRC_ROOT, PLUGINS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from home_assistant.interceptor import HomeAssistantDialogInterceptor
from model.plugin_resources import PluginResourceError, resource_reader_for_manifest
from model.plugin_router import PluginRouter
import model.plugin_router as plugin_router_module
from model.plugin_routing.interception import (
    InterceptRule,
    MAX_INTERCEPT_INPUT_CHARS,
    PluginDialogInterceptor,
    PluginInterceptionMetadataError,
    freeze_mapping,
    mutable_mapping,
    route_candidate_from_intercept,
)
from model.plugin_routing.models import (
    PluginExecutionPolicy,
    PluginManifest,
    PluginRouteCandidate,
    PluginRouteCapability,
    PluginRouteIntent,
)
from model.plugin_routing.handoff import PluginRoutingHandoff
from model.plugin_runtime import PluginExecutionResult
from weather.interceptor import WeatherDialogInterceptor


class _MemoryResourceReader:
    """In-memory resource reader for interceptor tests."""

    def __init__(self, text: str) -> None:
        self._text = text

    def read_text(self, relative_name: str, *, encoding: str = "utf-8") -> str:
        return self._text


class _ExampleInterceptor(PluginDialogInterceptor):
    """Minimal concrete interceptor for core behaviour tests."""

    def build_arguments(
        self,
        *,
        rule: InterceptRule,
        captures,
        original_text: str,
        normalised_text: str,
    ):
        return {**dict(rule.arguments), **dict(captures)}


class _FakeLogger:
    def log_debug(self, message: str) -> None:
        pass

    def log_info(self, message: str) -> None:
        pass

    def log_warning(self, message: str) -> None:
        pass

    def log_error(self, message: str) -> None:
        pass


class _FakeConfigManager:
    def config_value(self, section: str, key: str, default=None):
        return default


class _FakeContextManager:
    pass


class _FakePluginManager:
    def __init__(self, manifest: PluginManifest) -> None:
        self._manifest = manifest

    def get_manifest(self, plugin_id: str) -> PluginManifest | None:
        return self._manifest if plugin_id == self._manifest.plugin_id else None


def _manifest(
    *,
    capability_id: str = "alpha.capability",
    intent_name: str = "do_it",
    interceptor_entry_point: str | None = "interceptor:AlphaInterceptor",
    manifest_path: Path = Path("plugins/alpha.json"),
    plugin_dir: Path = Path("plugins/alpha"),
) -> PluginManifest:
    """Return a minimal manifest with one route."""
    return PluginManifest(
        schema_version=2,
        plugin_id="alpha",
        name="Alpha",
        description="Alpha test plugin",
        version="1.0.0",
        enabled=True,
        capabilities=(capability_id,),
        entitlements=(),
        entities=(),
        examples=(),
        entry_point="plugin:AlphaPlugin",
        manifest_path=manifest_path,
        plugin_dir=plugin_dir,
        manifest_hash="hash",
        execution_policy=PluginExecutionPolicy(
            action_type="informational_read_only",
            requires_confirmation=False,
            allowed_by_default=True,
            capabilities=(capability_id,),
            entitlements=(),
        ),
        route_capabilities=(
            PluginRouteCapability(
                capability_id=capability_id,
                intents=(
                    PluginRouteIntent(
                        name=intent_name,
                        safety_level="informational_read_only",
                    ),
                ),
            ),
        ),
        interceptor_entry_point=interceptor_entry_point,
    )


def _metadata(route_id: str = "do_it") -> str:
    """Return minimal valid interception metadata for one route."""
    return (
        "{"
        '"schema_version": 1,'
        '"rules": ['
        "{"
        '"rule_id": "alpha_exact",'
        f'"route_id": "{route_id}",'
        '"match_type": "exact_any",'
        '"priority": 10,'
        '"values": ["do it"],'
        '"arguments": {"nested": {"value": "original"}}'
        "}"
        "]"
        "}"
    )


def _regex_metadata(pattern: str) -> str:
    """Return interception metadata containing one regex rule."""
    return json.dumps(
        {
            "schema_version": 1,
            "rules": [
                {
                    "rule_id": "alpha_regex",
                    "route_id": "do_it",
                    "match_type": "regex",
                    "priority": 10,
                    "patterns": [pattern],
                }
            ],
        }
    )


class PluginDialogInterceptionTests(unittest.TestCase):
    """Verify shared dialogue interception behaviour."""

    def test_absent_route_id_fails_preparation(self) -> None:
        interceptor = _ExampleInterceptor(
            manifest=_manifest(),
            resources=_MemoryResourceReader(_metadata("missing_route")),
        )

        with self.assertRaises(PluginInterceptionMetadataError):
            interceptor.prepare()

    def test_oversized_metadata_is_rejected(self) -> None:
        interceptor = _ExampleInterceptor(
            manifest=_manifest(),
            resources=_MemoryResourceReader(" " * (64 * 1024 + 1)),
        )
        with self.assertRaisesRegex(PluginInterceptionMetadataError, "size limit"):
            interceptor.prepare()

    def test_unsafe_regex_constructs_are_rejected(self) -> None:
        patterns = {
            "unanchored": "do .+",
            "backreference": r"^(?P<word>.+) (?P=word)$",
            "lookbehind": r"^(?<=do )it$",
            "nested quantifier": r"^(a+)+$",
        }
        for label, pattern in patterns.items():
            with self.subTest(label=label):
                interceptor = _ExampleInterceptor(
                    manifest=_manifest(),
                    resources=_MemoryResourceReader(_regex_metadata(pattern)),
                )
                with self.assertRaises(PluginInterceptionMetadataError):
                    interceptor.prepare()

    def test_oversized_input_is_not_evaluated(self) -> None:
        interceptor = _ExampleInterceptor(
            manifest=_manifest(),
            resources=_MemoryResourceReader(_regex_metadata(r"^.+$")),
        )
        interceptor.prepare()
        self.assertIsNone(
            interceptor.intercept("a" * (MAX_INTERCEPT_INPUT_CHARS + 1))
        )

    def test_capability_and_intent_are_derived_from_manifest(self) -> None:
        manifest = _manifest(capability_id="alpha.changed_capability")
        interceptor = _ExampleInterceptor(
            manifest=manifest,
            resources=_MemoryResourceReader(_metadata()),
        )
        interceptor.prepare()

        match = interceptor.intercept("Do it")
        self.assertIsNotNone(match)
        candidate = route_candidate_from_intercept(match, manifest)

        self.assertEqual(candidate.capability_id, "alpha.changed_capability")
        self.assertEqual(candidate.intent_name, "do_it")

    def test_manifest_route_change_is_reflected_without_rule_change(self) -> None:
        manifest = _manifest(
            capability_id="alpha.new_capability",
            intent_name="do_it",
        )
        interceptor = _ExampleInterceptor(
            manifest=manifest,
            resources=_MemoryResourceReader(_metadata()),
        )
        interceptor.prepare()

        candidate = route_candidate_from_intercept(
            interceptor.intercept("do it"),
            manifest,
        )

        self.assertEqual(candidate.capability_id, "alpha.new_capability")

    def test_match_and_candidate_arguments_are_immutable_until_invocation(self) -> None:
        manifest = _manifest()
        interceptor = _ExampleInterceptor(
            manifest=manifest,
            resources=_MemoryResourceReader(_metadata()),
        )
        interceptor.prepare()
        match = interceptor.intercept("do it")
        candidate = route_candidate_from_intercept(match, manifest)

        with self.assertRaises(TypeError):
            match.arguments["new"] = "value"
        with self.assertRaises(TypeError):
            candidate.extracted_params["new"] = "value"

        invocation_arguments = mutable_mapping(candidate.extracted_params)
        invocation_arguments["nested"]["value"] = "changed"

        self.assertEqual(candidate.extracted_params["nested"]["value"], "original")

    def test_bundled_interceptors_do_not_override_template_method(self) -> None:
        self.assertNotIn("intercept", WeatherDialogInterceptor.__dict__)
        self.assertNotIn("intercept", HomeAssistantDialogInterceptor.__dict__)

    def test_migrated_router_does_not_invoke_deprecated_can_handle(self) -> None:
        manifest = _manifest()
        candidate = PluginRouteCandidate(
            plugin_id="alpha",
            capability_id="alpha.capability",
            intent_name="do_it",
            confidence=1.0,
            match_reasons=("dialog_intercept",),
            extracted_params=freeze_mapping({"nested": {"value": "original"}}),
            safety_level="informational_read_only",
            route_key="alpha::alpha.capability::do_it",
        )
        router = PluginRouter(
            plugin_manager=_FakePluginManager(manifest),
            logger=_FakeLogger(),
            config_mgr=_FakeConfigManager(),
            context_manager=_FakeContextManager(),
            plugin_db_session_factory=lambda: object(),
        )

        class _Plugin:
            def __init__(self, **kwargs) -> None:
                pass

            def can_handle(self, prompt: str) -> bool:
                raise AssertionError("can_handle must not be called")

            def execute(self, prompt: str, meta: dict):
                meta["plugin_route"]["arguments"]["nested"]["value"] = "changed"
                return PluginExecutionResult(
                    plugin_id="alpha",
                    content="handled",
                    provenance={},
                )

        original_loader = plugin_router_module.load_plugin_class
        plugin_router_module.load_plugin_class = lambda loaded_manifest: _Plugin
        try:
            result = router.route(
                "do it",
                {},
                PluginRoutingHandoff(candidates=(candidate,), refreshed=False),
                "unit_user",
            )
        finally:
            plugin_router_module.load_plugin_class = original_loader

        self.assertIsNotNone(result)
        self.assertEqual(candidate.extracted_params["nested"]["value"], "original")

    def test_bound_resource_reader_rejects_symlink_escape(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            tempfile.TemporaryDirectory() as external_dir,
        ):
            root = Path(temp_dir)
            plugin_dir = root / "alpha"
            plugin_dir.mkdir()
            manifest = _manifest(
                manifest_path=root / "alpha.json",
                plugin_dir=plugin_dir,
            )
            external = Path(external_dir)
            external_resource = external / "intercept_meta.json"
            external_resource.write_text("{}", encoding="utf-8")

            with self.subTest("resources root"):
                (plugin_dir / "resources").symlink_to(
                    external,
                    target_is_directory=True,
                )
                reader = resource_reader_for_manifest(manifest)
                with self.assertRaises(PluginResourceError):
                    reader.read_text("intercept_meta.json")
                (plugin_dir / "resources").unlink()

            with self.subTest("resource file"):
                resources = plugin_dir / "resources"
                resources.mkdir()
                (resources / "intercept_meta.json").symlink_to(external_resource)
                reader = resource_reader_for_manifest(manifest)
                with self.assertRaises(PluginResourceError):
                    reader.read_text("intercept_meta.json")


if __name__ == "__main__":
    unittest.main()
