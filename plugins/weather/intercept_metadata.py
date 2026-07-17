"""Load and evaluate declarative plugin interception metadata."""
# Author: Clive Bostock
# Date: 2026-07-15
# Description: Loads validated plugin-owned interception rules and returns structured matches.

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping, Pattern

from model.plugin_resources import manifest_for_plugin_module
from model.plugin_resources import resolve_plugin_resource
from model.plugin_routing.models import PluginManifest

__author__ = "Clive Bostock"
__date__ = "2026-07-15"
__description__ = (
    "Loads validated plugin-owned interception rules and returns structured "
    "matches from resources/intercept_meta.json."
)


class InterceptMetadataError(ValueError):
    """Raised when plugin interception metadata is missing or invalid."""


@dataclass(frozen=True)
class InterceptMatch:
    """Describe one declarative interception rule matched by a prompt.

    Attributes:
        rule_id: Stable identifier for the matching rule.
        intent: Optional intent assigned by the plugin metadata.
        captures: Named regular-expression captures extracted from the prompt.
        parameters: Fixed parameters declared on the matching metadata rule.
    """

    rule_id: str
    intent: str | None = None
    captures: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )
    parameters: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )


@dataclass(frozen=True)
class _CompiledRule:
    """Store one validated rule and any compiled regular expressions."""

    rule_id: str
    match_type: str
    values: tuple[str, ...]
    patterns: tuple[Pattern[str], ...]
    priority: int
    intent: str | None
    parameters: Mapping[str, Any]


class InterceptMetadata:
    """Evaluate plugin-owned deterministic interception rules."""

    _SUPPORTED_MATCH_TYPES = {"contains_any", "exact_any", "regex_any"}

    def __init__(self, metadata_path: Path) -> None:
        """Load and validate interception metadata.

        Args:
            metadata_path: Path to the plugin's ``intercept_meta.json`` file.

        Raises:
            InterceptMetadataError: If the file cannot be loaded or is invalid.
        """
        self._metadata_path = metadata_path
        metadata = self._load_metadata(metadata_path)
        self._normalisation = str(metadata.get("normalisation") or "spoken_command")
        if self._normalisation != "spoken_command":
            raise InterceptMetadataError(
                f"Unsupported normalisation '{self._normalisation}' in {metadata_path}."
            )
        self._normalisation_replacements = self._load_normalisation_replacements(
            metadata.get("normalisation_replacements", {})
        )
        self._exclusions = self._compile_rules(
            metadata.get("exclusions", []),
            section="exclusions",
        )
        self._rules = self._compile_rules(metadata.get("rules", []), section="rules")
        if not self._rules:
            raise InterceptMetadataError(
                f"No interception rules were defined in {metadata_path}."
            )
        self._validate_test_cases(metadata.get("tests", {}))

    @classmethod
    def from_plugin_manifest(cls, manifest: PluginManifest) -> "InterceptMetadata":
        """Load metadata from the active plugin manifest resources directory."""
        return cls(resolve_plugin_resource(manifest, "intercept_meta.json"))

    @classmethod
    def from_plugin_module(cls, module_file: str) -> "InterceptMetadata":
        """Load metadata through a manifest discovered beside a plugin module.

        Args:
            module_file: ``__file__`` value from a module inside the plugin.

        Returns:
            Loaded and validated interception metadata.
        """
        manifest = manifest_for_plugin_module(module_file, "weather")
        return cls.from_plugin_manifest(manifest)

    def matches(self, prompt: str) -> bool:
        """Return whether any non-excluded rule matches the prompt.

        Args:
            prompt: User prompt to evaluate.

        Returns:
            ``True`` when the plugin should intercept the prompt.
        """
        return self.match(prompt) is not None

    def match(self, prompt: str) -> InterceptMatch | None:
        """Return structured details of the first matching interception rule.

        Args:
            prompt: User prompt to evaluate.

        Returns:
            Match details including named captures and fixed parameters, or
            ``None`` when the prompt should continue normally.
        """
        text = self.normalise(prompt)
        if not text:
            return None
        if any(self._match_rule(rule, text) is not None for rule in self._exclusions):
            return None
        for rule in self._rules:
            captures = self._match_rule(rule, text)
            if captures is None:
                continue
            return InterceptMatch(
                rule_id=rule.rule_id,
                intent=rule.intent,
                captures=MappingProxyType(captures),
                parameters=rule.parameters,
            )
        return None

    def exact_values(self, rule_id: str) -> frozenset[str]:
        """Return the canonical values from one ``exact_any`` rule.

        Args:
            rule_id: Stable rule identifier from the metadata.

        Returns:
            Canonical exact values belonging to the rule.

        Raises:
            InterceptMetadataError: If the rule is absent or has another type.
        """
        for rule in self._rules:
            if rule.rule_id != rule_id:
                continue
            if rule.match_type != "exact_any":
                raise InterceptMetadataError(
                    f"Rule '{rule_id}' is not an exact_any rule."
                )
            return frozenset(rule.values)
        raise InterceptMetadataError(f"Rule '{rule_id}' was not found.")

    def normalise(self, value: Any) -> str:
        """Return canonical spoken-command text for deterministic matching.

        Args:
            value: Prompt or metadata value to normalise.

        Returns:
            Lowercase, whitespace-normalised spoken-command text.
        """
        text = str(value or "").casefold().strip()
        text = re.sub(r"[^a-z0-9'_.%°\s-]", " ", text)
        text = re.sub(r"\s+", " ", text).strip(" .-?")
        for source, replacement in self._normalisation_replacements.items():
            text = re.sub(rf"\b{re.escape(source)}\b", replacement, text)
        return re.sub(r"\s+", " ", text).strip(" .-?")

    def _validate_test_cases(self, raw_tests: Any) -> None:
        """Validate embedded interception examples and structured matches.

        Args:
            raw_tests: Optional ``tests`` object from the metadata document.

        Raises:
            InterceptMetadataError: If a test collection is malformed or fails.
        """
        if not isinstance(raw_tests, dict):
            raise InterceptMetadataError(
                f"'tests' must be a JSON object in {self._metadata_path}."
            )
        should_match = self._test_string_list(raw_tests, "should_match")
        should_not_match = self._test_string_list(raw_tests, "should_not_match")
        failed_positive = [prompt for prompt in should_match if not self.matches(prompt)]
        failed_negative = [prompt for prompt in should_not_match if self.matches(prompt)]
        failed_structured = self._failed_structured_tests(raw_tests.get("match_cases", []))
        if failed_positive or failed_negative or failed_structured:
            details = []
            if failed_positive:
                details.append(f"missed expected prompts: {failed_positive}")
            if failed_negative:
                details.append(f"claimed excluded prompts: {failed_negative}")
            if failed_structured:
                details.append(f"structured match failures: {failed_structured}")
            raise InterceptMetadataError(
                f"Embedded interception tests failed in {self._metadata_path}: "
                + "; ".join(details)
            )

    def _failed_structured_tests(self, raw_cases: Any) -> list[str]:
        """Return descriptions of failed structured metadata match tests."""
        if not isinstance(raw_cases, list):
            raise InterceptMetadataError(
                "Interception test field 'match_cases' must be an array of objects."
            )
        failures: list[str] = []
        for index, raw_case in enumerate(raw_cases):
            if not isinstance(raw_case, dict):
                raise InterceptMetadataError(
                    f"Interception match_cases[{index}] must be a JSON object."
                )
            prompt = raw_case.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                raise InterceptMetadataError(
                    f"Interception match_cases[{index}].prompt must be a string."
                )
            expected_rule_id = raw_case.get("rule_id")
            expected_intent = raw_case.get("intent")
            expected_captures = raw_case.get("captures", {})
            expected_parameters = raw_case.get("parameters", {})
            if not isinstance(expected_captures, dict) or not isinstance(
                expected_parameters, dict
            ):
                raise InterceptMetadataError(
                    f"Interception match_cases[{index}] captures and parameters "
                    "must be JSON objects."
                )
            match = self.match(prompt)
            actual = None
            if match is not None:
                actual = {
                    "rule_id": match.rule_id,
                    "intent": match.intent,
                    "captures": dict(match.captures),
                    "parameters": dict(match.parameters),
                }
            expected = {
                "rule_id": expected_rule_id,
                "intent": expected_intent,
                "captures": expected_captures,
                "parameters": expected_parameters,
            }
            if actual != expected:
                failures.append(
                    f"case {index} prompt={prompt!r} expected={expected!r} "
                    f"actual={actual!r}"
                )
        return failures

    @staticmethod
    def _test_string_list(raw_tests: dict[str, Any], key: str) -> tuple[str, ...]:
        """Return one validated embedded test list."""
        value = raw_tests.get(key, [])
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise InterceptMetadataError(
                f"Interception test field '{key}' must be an array of strings."
            )
        return tuple(item for item in value if item.strip())

    @staticmethod
    def _load_normalisation_replacements(raw_replacements: Any) -> Mapping[str, str]:
        """Return validated typo/variant replacements for spoken text."""
        if not isinstance(raw_replacements, dict):
            raise InterceptMetadataError(
                "'normalisation_replacements' must be a JSON object."
            )
        replacements: dict[str, str] = {}
        for source, replacement in raw_replacements.items():
            source_text = str(source or "").casefold().strip()
            replacement_text = str(replacement or "").casefold().strip()
            if not source_text or not replacement_text:
                raise InterceptMetadataError(
                    "'normalisation_replacements' entries must be non-empty strings."
                )
            replacements[source_text] = replacement_text
        return MappingProxyType(replacements)

    @staticmethod
    def _load_metadata(metadata_path: Path) -> dict[str, Any]:
        """Read one metadata document from disk."""
        try:
            with metadata_path.open("r", encoding="utf-8") as handle:
                metadata = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise InterceptMetadataError(
                f"Unable to load interception metadata {metadata_path}: {exc}"
            ) from exc
        if not isinstance(metadata, dict):
            raise InterceptMetadataError(
                f"Interception metadata must be a JSON object: {metadata_path}."
            )
        if metadata.get("schema_version") != 1:
            raise InterceptMetadataError(
                f"Unsupported interception schema version in {metadata_path}."
            )
        return metadata

    def _compile_rules(
        self,
        raw_rules: Any,
        *,
        section: str,
    ) -> tuple[_CompiledRule, ...]:
        """Validate and compile one metadata rule collection."""
        if not isinstance(raw_rules, list):
            raise InterceptMetadataError(
                f"'{section}' must be a JSON array in {self._metadata_path}."
            )
        compiled: list[_CompiledRule] = []
        seen_ids: set[str] = set()
        for index, raw_rule in enumerate(raw_rules):
            if not isinstance(raw_rule, dict):
                raise InterceptMetadataError(
                    f"{section}[{index}] must be a JSON object."
                )
            rule_id = str(raw_rule.get("id") or "").strip()
            if not rule_id or rule_id in seen_ids:
                raise InterceptMetadataError(
                    f"Invalid or duplicate rule id '{rule_id}' in {section}."
                )
            seen_ids.add(rule_id)
            match_type = str(raw_rule.get("match_type") or "").strip()
            if match_type not in self._SUPPORTED_MATCH_TYPES:
                raise InterceptMetadataError(
                    f"Unsupported match_type '{match_type}' for rule '{rule_id}'."
                )
            values = tuple(
                self.normalise(value)
                for value in self._require_string_list(raw_rule, "values", rule_id)
            )
            raw_patterns = self._require_string_list(raw_rule, "patterns", rule_id)
            patterns: list[Pattern[str]] = []
            for raw_pattern in raw_patterns:
                try:
                    patterns.append(re.compile(raw_pattern))
                except re.error as exc:
                    raise InterceptMetadataError(
                        f"Invalid regex in rule '{rule_id}': {exc}."
                    ) from exc
            if match_type in {"contains_any", "exact_any"} and not values:
                raise InterceptMetadataError(
                    f"Rule '{rule_id}' requires at least one value."
                )
            if match_type == "regex_any" and not patterns:
                raise InterceptMetadataError(
                    f"Rule '{rule_id}' requires at least one pattern."
                )
            priority = raw_rule.get("priority", 0)
            if not isinstance(priority, int):
                raise InterceptMetadataError(
                    f"Rule '{rule_id}' priority must be an integer."
                )
            intent_value = raw_rule.get("intent")
            intent = str(intent_value).strip() if intent_value is not None else None
            raw_parameters = raw_rule.get("parameters", {})
            if not isinstance(raw_parameters, dict):
                raise InterceptMetadataError(
                    f"Rule '{rule_id}' parameters must be a JSON object."
                )
            compiled.append(
                _CompiledRule(
                    rule_id=rule_id,
                    match_type=match_type,
                    values=values,
                    patterns=tuple(patterns),
                    priority=priority,
                    intent=intent or None,
                    parameters=MappingProxyType(dict(raw_parameters)),
                )
            )
        return tuple(sorted(compiled, key=lambda rule: rule.priority, reverse=True))

    @staticmethod
    def _require_string_list(
        raw_rule: dict[str, Any],
        key: str,
        rule_id: str,
    ) -> tuple[str, ...]:
        """Return one optional metadata list after validating string members."""
        value = raw_rule.get(key, [])
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise InterceptMetadataError(
                f"Rule '{rule_id}' field '{key}' must be an array of strings."
            )
        return tuple(item for item in value if item.strip())

    @staticmethod
    def _match_rule(rule: _CompiledRule, text: str) -> dict[str, str] | None:
        """Return named captures when one compiled rule matches canonical text."""
        if rule.match_type == "exact_any":
            return {} if text in rule.values else None
        if rule.match_type == "contains_any":
            return {} if any(value in text for value in rule.values) else None
        if rule.match_type == "regex_any":
            for pattern in rule.patterns:
                match = pattern.fullmatch(text)
                if match is None:
                    continue
                return {
                    name: value.strip()
                    for name, value in match.groupdict().items()
                    if value is not None and value.strip()
                }
        return None
