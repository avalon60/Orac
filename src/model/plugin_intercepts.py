"""Evaluate declarative plugin interception metadata for core routing."""
# Author: Clive Bostock
# Date: 17-Jul-2026
# Description: Loads safe plugin resource rules used to boost routing candidates.

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping, Pattern


class PluginInterceptMetadataError(ValueError):
    """Raised when plugin interception metadata is malformed."""


@dataclass(frozen=True)
class PluginInterceptMatch:
    """Represents one deterministic plugin interception match."""

    rule_id: str
    intent: str | None = None
    captures: Mapping[str, str] = field(
        default_factory=lambda: MappingProxyType({})
    )
    parameters: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )


@dataclass(frozen=True)
class _CompiledInterceptRule:
    """Stores one validated interception rule."""

    rule_id: str
    match_type: str
    values: tuple[str, ...]
    patterns: tuple[Pattern[str], ...]
    priority: int
    intent: str | None
    parameters: Mapping[str, Any]


class PluginInterceptMetadata:
    """Evaluate Orac-owned deterministic routing rules from plugin resources."""

    _SUPPORTED_MATCH_TYPES = {"contains_any", "exact_any", "regex_any"}

    def __init__(self, metadata_path: Path) -> None:
        """Load and validate one ``resources/intercept_meta.json`` file."""
        self._metadata_path = metadata_path
        metadata = self._load_metadata(metadata_path)
        self._normalisation = str(metadata.get("normalisation") or "spoken_command")
        if self._normalisation != "spoken_command":
            raise PluginInterceptMetadataError(
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
            raise PluginInterceptMetadataError(
                f"No interception rules were defined in {metadata_path}."
            )
        self._validate_test_cases(metadata.get("tests", {}))

    def match(self, prompt: str) -> PluginInterceptMatch | None:
        """Return structured details when a prompt matches a resource rule."""
        text = self.normalise(prompt)
        if not text:
            return None
        if any(self._match_rule(rule, text) is not None for rule in self._exclusions):
            return None
        for rule in self._rules:
            captures = self._match_rule(rule, text)
            if captures is None:
                continue
            return PluginInterceptMatch(
                rule_id=rule.rule_id,
                intent=rule.intent,
                captures=MappingProxyType(captures),
                parameters=rule.parameters,
            )
        return None

    def normalise(self, value: Any) -> str:
        """Return canonical spoken-command text for deterministic matching."""
        text = str(value or "").casefold().strip()
        text = re.sub(r"[^a-z0-9'_.%°\s-]", " ", text)
        text = re.sub(r"\s+", " ", text).strip(" .-?")
        for source, replacement in self._normalisation_replacements.items():
            text = re.sub(rf"\b{re.escape(source)}\b", replacement, text)
        return re.sub(r"\s+", " ", text).strip(" .-?")

    def _validate_test_cases(self, raw_tests: Any) -> None:
        """Validate embedded metadata examples at load time."""
        if not isinstance(raw_tests, dict):
            raise PluginInterceptMetadataError(
                f"'tests' must be a JSON object in {self._metadata_path}."
            )
        should_match = self._test_string_list(raw_tests, "should_match")
        should_not_match = self._test_string_list(raw_tests, "should_not_match")
        failed_positive = [
            prompt for prompt in should_match if self.match(prompt) is None
        ]
        failed_negative = [
            prompt for prompt in should_not_match if self.match(prompt) is not None
        ]
        failed_structured = self._failed_structured_tests(raw_tests.get("match_cases", []))
        if failed_positive or failed_negative or failed_structured:
            details = []
            if failed_positive:
                details.append(f"missed expected prompts: {failed_positive}")
            if failed_negative:
                details.append(f"claimed excluded prompts: {failed_negative}")
            if failed_structured:
                details.append(f"structured match failures: {failed_structured}")
            raise PluginInterceptMetadataError(
                f"Embedded interception tests failed in {self._metadata_path}: "
                + "; ".join(details)
            )

    def _failed_structured_tests(self, raw_cases: Any) -> list[str]:
        """Return descriptions of structured test cases that failed."""
        if not isinstance(raw_cases, list):
            raise PluginInterceptMetadataError(
                "Interception test field 'match_cases' must be an array of objects."
            )
        failures: list[str] = []
        for index, raw_case in enumerate(raw_cases):
            if not isinstance(raw_case, dict):
                raise PluginInterceptMetadataError(
                    f"Interception match_cases[{index}] must be a JSON object."
                )
            prompt = raw_case.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                raise PluginInterceptMetadataError(
                    f"Interception match_cases[{index}].prompt must be a string."
                )
            expected = {
                "rule_id": raw_case.get("rule_id"),
                "intent": raw_case.get("intent"),
                "captures": raw_case.get("captures", {}),
                "parameters": raw_case.get("parameters", {}),
            }
            if not isinstance(expected["captures"], dict) or not isinstance(
                expected["parameters"], dict
            ):
                raise PluginInterceptMetadataError(
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
            raise PluginInterceptMetadataError(
                f"Interception test field '{key}' must be an array of strings."
            )
        return tuple(item for item in value if item.strip())

    @staticmethod
    def _load_normalisation_replacements(raw_replacements: Any) -> Mapping[str, str]:
        """Return validated typo and variant replacements."""
        if not isinstance(raw_replacements, dict):
            raise PluginInterceptMetadataError(
                "'normalisation_replacements' must be a JSON object."
            )
        replacements: dict[str, str] = {}
        for source, replacement in raw_replacements.items():
            source_text = str(source or "").casefold().strip()
            replacement_text = str(replacement or "").casefold().strip()
            if not source_text or not replacement_text:
                raise PluginInterceptMetadataError(
                    "'normalisation_replacements' entries must be non-empty strings."
                )
            replacements[source_text] = replacement_text
        return MappingProxyType(replacements)

    @classmethod
    def _compile_rules(
        cls,
        raw_rules: Any,
        *,
        section: str,
    ) -> tuple[_CompiledInterceptRule, ...]:
        """Validate and compile one rule section."""
        if not isinstance(raw_rules, list):
            raise PluginInterceptMetadataError(f"'{section}' must be an array.")
        rules: list[_CompiledInterceptRule] = []
        for index, raw_rule in enumerate(raw_rules):
            if not isinstance(raw_rule, dict):
                raise PluginInterceptMetadataError(
                    f"{section}[{index}] must be a JSON object."
                )
            rule_id = str(raw_rule.get("id") or "").strip()
            match_type = str(raw_rule.get("match_type") or "").strip()
            if not rule_id:
                raise PluginInterceptMetadataError(
                    f"{section}[{index}].id must be a non-empty string."
                )
            if match_type not in cls._SUPPORTED_MATCH_TYPES:
                raise PluginInterceptMetadataError(
                    f"{section}[{index}].match_type '{match_type}' is unsupported."
                )
            values = cls._string_tuple(raw_rule.get("values", ()), section, index, "values")
            raw_patterns = cls._string_tuple(
                raw_rule.get("patterns", ()),
                section,
                index,
                "patterns",
            )
            if match_type in {"contains_any", "exact_any"} and not values:
                raise PluginInterceptMetadataError(
                    f"{section}[{index}].values must be non-empty for {match_type}."
                )
            if match_type == "regex_any" and not raw_patterns:
                raise PluginInterceptMetadataError(
                    f"{section}[{index}].patterns must be non-empty for regex_any."
                )
            parameters = raw_rule.get("parameters", {})
            if not isinstance(parameters, dict):
                raise PluginInterceptMetadataError(
                    f"{section}[{index}].parameters must be a JSON object."
                )
            rules.append(
                _CompiledInterceptRule(
                    rule_id=rule_id,
                    match_type=match_type,
                    values=tuple(value.casefold().strip() for value in values),
                    patterns=tuple(
                        re.compile(pattern, flags=re.IGNORECASE)
                        for pattern in raw_patterns
                    ),
                    priority=int(raw_rule.get("priority", 0)),
                    intent=str(raw_rule.get("intent") or "").strip() or None,
                    parameters=MappingProxyType(dict(parameters)),
                )
            )
        return tuple(sorted(rules, key=lambda rule: rule.priority, reverse=True))

    @staticmethod
    def _string_tuple(
        value: Any,
        section: str,
        index: int,
        field_name: str,
    ) -> tuple[str, ...]:
        """Return a validated tuple of non-empty strings."""
        if value in (None, ()):
            return ()
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise PluginInterceptMetadataError(
                f"{section}[{index}].{field_name} must be an array of strings."
            )
        return tuple(item.strip() for item in value if item.strip())

    @staticmethod
    def _load_metadata(metadata_path: Path) -> dict[str, Any]:
        """Read one metadata JSON object from disk."""
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise PluginInterceptMetadataError(
                f"Could not read interception metadata {metadata_path}: {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise PluginInterceptMetadataError(
                f"Could not parse interception metadata {metadata_path}: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise PluginInterceptMetadataError(
                f"Interception metadata must be a JSON object: {metadata_path}"
            )
        return payload

    @staticmethod
    def _match_rule(
        rule: _CompiledInterceptRule,
        text: str,
    ) -> dict[str, str] | None:
        """Return captures when text matches a compiled rule."""
        if rule.match_type == "exact_any":
            return {} if text in rule.values else None
        if rule.match_type == "contains_any":
            return {} if any(value in text for value in rule.values) else None
        for pattern in rule.patterns:
            match = pattern.search(text)
            if match:
                return {
                    key: value
                    for key, value in match.groupdict().items()
                    if value is not None
                }
        return None
