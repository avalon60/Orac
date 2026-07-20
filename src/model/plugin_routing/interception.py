"""Shared core dialogue interception for plugin routing."""
# Author: Clive Bostock
# Date: 17-Jul-2026
# Description: Defines core-owned plugin dialogue matching and route evidence.

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
import json
import re
from types import MappingProxyType
from typing import Any, Literal, Pattern, Protocol

from model.plugin_routing.models import (
    PluginManifest,
    PluginRouteCandidate,
    PluginRouteCapability,
    PluginRouteIntent,
)


InterceptMatchType = Literal["exact_any", "regex"]
DETERMINISTIC_INTERCEPT_CONFIDENCE = 1.0
MAX_INTERCEPT_METADATA_BYTES = 64 * 1024
MAX_INTERCEPT_RULES = 100
MAX_EXACT_VALUES_PER_RULE = 100
MAX_REGEX_PATTERNS_PER_RULE = 32
MAX_EXACT_VALUE_CHARS = 256
MAX_REGEX_PATTERN_CHARS = 512
MAX_NORMALISATION_REPLACEMENTS = 100
MAX_NORMALISATION_REPLACEMENT_CHARS = 128
MAX_INTERCEPT_INPUT_CHARS = 2048

_REGEX_BACKREFERENCE = re.compile(r"\\(?:[1-9][0-9]*|g<[^>]+>)|\(\?P=[^)]+\)")
_REGEX_LOOKBEHIND = re.compile(r"\(\?<(?:=|!)")
_REGEX_NESTED_QUANTIFIER = re.compile(
    r"\((?:\\.|[^()])*?(?:\*|\+|\{\d*,?\d*\})(?:\\.|[^()])*?\)\s*(?:\*|\+|\{)"
)


class PluginResourceReader(Protocol):
    """Read immutable plugin resources needed by an interceptor."""

    def read_text(self, relative_name: str, *, encoding: str = "utf-8") -> str:
        """Read one resource as text."""


class PluginDialogInterceptionError(RuntimeError):
    """Base class for plugin dialogue interception failures."""


class PluginInterceptionConfigurationError(PluginDialogInterceptionError):
    """Raised when an interceptor is used before successful preparation."""


class PluginInterceptionMetadataError(PluginDialogInterceptionError, ValueError):
    """Raised when interception metadata is missing or malformed."""


@dataclass(frozen=True)
class InterceptNormalisation:
    """Core-owned normalisation configuration for dialogue matching."""

    mode: str = "spoken_command"
    replacements: Mapping[str, str] = MappingProxyType({})


@dataclass(frozen=True)
class InterceptRule:
    """One validated dialogue matching rule from plugin resources."""

    rule_id: str
    route_id: str
    match_type: InterceptMatchType
    priority: int
    values: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()
    arguments: Mapping[str, Any] = MappingProxyType({})
    declaration_order: int = 0


@dataclass(frozen=True)
class InterceptMetadata:
    """Parsed immutable interception metadata."""

    schema_version: int
    normalisation: InterceptNormalisation
    rules: tuple[InterceptRule, ...]
    source_hash: str


@dataclass(frozen=True)
class CompiledInterceptRule:
    """Runtime-prepared interception rule with compiled regular expressions."""

    rule: InterceptRule
    exact_values: tuple[str, ...]
    patterns: tuple[Pattern[str], ...]


@dataclass(frozen=True)
class CompiledInterceptMetadata:
    """Prepared immutable interception metadata used during request routing."""

    metadata: InterceptMetadata
    rules: tuple[CompiledInterceptRule, ...]


@dataclass(frozen=True)
class InterceptMatch:
    """Core-owned immutable evidence that one interceptor matched an utterance."""

    plugin_id: str
    route_id: str
    rule_id: str
    match_type: InterceptMatchType
    arguments: Mapping[str, Any]
    original_text: str
    normalised_text: str
    priority: int


@dataclass(frozen=True)
class ManifestRoute:
    """One manifest route addressable by interception metadata."""

    route_id: str
    capability: PluginRouteCapability
    intent: PluginRouteIntent


@dataclass(frozen=True)
class _RawRuleMatch:
    """Internal syntactic rule match before plugin argument construction."""

    rule: InterceptRule
    captures: Mapping[str, str]

    @property
    def rank(self) -> tuple[int, int]:
        """Return local selection rank for priority and specificity."""
        specificity = 1 if self.rule.match_type == "exact_any" else 0
        return self.rule.priority, specificity


class PluginDialogInterceptor(ABC):
    """Template-method superclass for deterministic plugin dialogue matching."""

    METADATA_RESOURCE_NAME = "intercept_meta.json"

    def __init__(
        self,
        *,
        manifest: PluginManifest,
        resources: PluginResourceReader,
        logger: Any | None = None,
    ) -> None:
        """Initialise the interceptor with core-owned dependencies only."""
        self.manifest = manifest
        self.resources = resources
        self.logger = logger
        self._prepared_metadata: CompiledInterceptMetadata | None = None
        self._route_lookup: Mapping[str, ManifestRoute] = MappingProxyType({})

    def prepare(self) -> None:
        """Load, validate, and compile metadata once for request-time matching."""
        source = self.resources.read_text(self.METADATA_RESOURCE_NAME)
        route_lookup = manifest_route_lookup(self.manifest)
        metadata = parse_intercept_metadata(source, route_lookup=route_lookup)
        self._prepared_metadata = compile_intercept_metadata(metadata)
        self._route_lookup = route_lookup

    def intercept(self, user_text: str) -> InterceptMatch | None:
        """Return an immutable match when plugin metadata and hook accept text."""
        original_text = str(user_text or "")
        if not original_text.strip():
            return None
        if len(original_text) > MAX_INTERCEPT_INPUT_CHARS:
            _log_warning(
                self.logger,
                "Plugin dialogue interception skipped input exceeding the "
                f"{MAX_INTERCEPT_INPUT_CHARS}-character limit.",
            )
            return None
        if self._prepared_metadata is None:
            raise PluginInterceptionConfigurationError(
                f"Plugin '{self.manifest.plugin_id}' interceptor was not prepared."
            )

        normalised_text = normalise_text(
            original_text,
            self._prepared_metadata.metadata.normalisation,
        )
        if not normalised_text:
            return None

        raw_matches = _evaluate_rules(self._prepared_metadata, normalised_text)
        if not raw_matches:
            return None

        best_rank = max(match.rank for match in raw_matches)
        best_matches = [
            match for match in raw_matches if match.rank == best_rank
        ]
        accepted: list[tuple[_RawRuleMatch, Mapping[str, Any]]] = []
        for raw_match in best_matches:
            try:
                arguments = self.build_arguments(
                    rule=raw_match.rule,
                    captures=raw_match.captures,
                    original_text=original_text,
                    normalised_text=normalised_text,
                )
            except Exception as exc:
                _log_warning(
                    self.logger,
                    "Plugin dialogue interceptor hook failed for "
                    f"'{self.manifest.plugin_id}' rule "
                    f"'{raw_match.rule.rule_id}': {exc}",
                )
                return None
            if arguments is None:
                continue
            accepted.append((raw_match, freeze_mapping(arguments)))

        if not accepted:
            return None
        selected_match, selected_arguments = _select_accepted_match(
            self.manifest.plugin_id,
            accepted,
            logger=self.logger,
        )
        if selected_match is None:
            return None
        return InterceptMatch(
            plugin_id=self.manifest.plugin_id,
            route_id=selected_match.rule.route_id,
            rule_id=selected_match.rule.rule_id,
            match_type=selected_match.rule.match_type,
            arguments=selected_arguments,
            original_text=original_text,
            normalised_text=normalised_text,
            priority=selected_match.rule.priority,
        )

    @abstractmethod
    def build_arguments(
        self,
        *,
        rule: InterceptRule,
        captures: Mapping[str, str],
        original_text: str,
        normalised_text: str,
    ) -> Mapping[str, Any] | None:
        """Return route arguments or ``None`` when plugin validation rejects."""


class PluginInterceptionRegistry:
    """Immutable registry of prepared dialogue interceptors."""

    def __init__(
        self,
        entries: Mapping[str, tuple[PluginManifest, PluginDialogInterceptor]],
        *,
        logger: Any | None = None,
    ) -> None:
        """Initialise the registry from prepared interceptors."""
        self._entries = MappingProxyType(dict(entries))
        self._logger = logger

    def __len__(self) -> int:
        """Return the number of healthy prepared interceptors."""
        return len(self._entries)

    def candidates_for(self, utterance: str) -> tuple[PluginRouteCandidate, ...]:
        """Return deterministic route candidates for all matching interceptors."""
        candidates: list[PluginRouteCandidate] = []
        for plugin_id, (manifest, interceptor) in self._entries.items():
            try:
                match = interceptor.intercept(utterance)
            except PluginDialogInterceptionError as exc:
                _log_warning(
                    self._logger,
                    f"Plugin dialogue interceptor skipped '{plugin_id}': {exc}",
                )
                continue
            except Exception as exc:
                _log_warning(
                    self._logger,
                    "Plugin dialogue interceptor failed unexpectedly for "
                    f"'{plugin_id}': {exc}",
                )
                continue
            if match is None:
                continue
            candidates.append(route_candidate_from_intercept(match, manifest))
        return tuple(candidates)


def parse_intercept_metadata(
    source: str,
    *,
    route_lookup: Mapping[str, ManifestRoute],
) -> InterceptMetadata:
    """Parse and validate one interception metadata document."""
    if len(source.encode("utf-8")) > MAX_INTERCEPT_METADATA_BYTES:
        raise PluginInterceptionMetadataError(
            "Interception metadata exceeds the 64 KiB size limit."
        )
    try:
        raw = json.loads(source)
    except json.JSONDecodeError as exc:
        raise PluginInterceptionMetadataError(
            f"Could not parse interception metadata: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise PluginInterceptionMetadataError(
            "Interception metadata must be a JSON object."
        )
    schema_version = raw.get("schema_version")
    if schema_version != 1:
        raise PluginInterceptionMetadataError(
            "Interception metadata schema_version must be 1."
        )
    normalisation = _parse_normalisation(raw)
    rules = _parse_rules(raw.get("rules"), route_lookup=route_lookup)
    if not rules:
        raise PluginInterceptionMetadataError(
            "Interception metadata must define at least one rule."
        )
    import hashlib

    return InterceptMetadata(
        schema_version=1,
        normalisation=normalisation,
        rules=rules,
        source_hash=hashlib.sha256(source.encode("utf-8")).hexdigest(),
    )


def compile_intercept_metadata(
    metadata: InterceptMetadata,
) -> CompiledInterceptMetadata:
    """Compile regular expressions and normalised exact values."""
    compiled: list[CompiledInterceptRule] = []
    for rule in metadata.rules:
        exact_values = tuple(
            normalise_text(value, metadata.normalisation)
            for value in rule.values
        )
        patterns = []
        for pattern in rule.patterns:
            _validate_safe_regex(pattern, rule_id=rule.rule_id)
            try:
                patterns.append(re.compile(pattern, flags=re.IGNORECASE))
            except re.error as exc:
                raise PluginInterceptionMetadataError(
                    f"Invalid regex for rule '{rule.rule_id}': {exc}"
                ) from exc
        compiled.append(
            CompiledInterceptRule(
                rule=rule,
                exact_values=exact_values,
                patterns=tuple(patterns),
            )
        )
    return CompiledInterceptMetadata(metadata=metadata, rules=tuple(compiled))


def manifest_route_lookup(manifest: PluginManifest) -> Mapping[str, ManifestRoute]:
    """Return manifest routes keyed by unique intent name route IDs."""
    routes: dict[str, ManifestRoute] = {}
    duplicates: set[str] = set()
    for capability in manifest.route_capabilities:
        for intent in capability.intents:
            route_id = intent.name
            if route_id in routes:
                duplicates.add(route_id)
                continue
            routes[route_id] = ManifestRoute(
                route_id=route_id,
                capability=capability,
                intent=intent,
            )
    if duplicates:
        raise PluginInterceptionMetadataError(
            "Manifest route intent names must be unique for interception: "
            + ", ".join(sorted(duplicates))
        )
    return MappingProxyType(routes)


def route_candidate_from_intercept(
    match: InterceptMatch,
    manifest: PluginManifest,
) -> PluginRouteCandidate:
    """Convert immutable intercept evidence into an arbitration candidate."""
    route = manifest_route_lookup(manifest).get(match.route_id)
    if route is None:
        raise PluginInterceptionMetadataError(
            f"Interception route_id '{match.route_id}' is absent from manifest."
        )
    policy = manifest.execution_policy
    safety_level = str(
        route.intent.safety_level
        or (policy.action_type if policy is not None else "informational_read_only")
    )
    requires_confirmation = bool(
        route.intent.requires_confirmation
        if route.intent.requires_confirmation is not None
        else (policy.requires_confirmation if policy is not None else False)
    )
    route_key = f"{manifest.plugin_id}::{route.capability.capability_id}::{route.intent.name}"
    return PluginRouteCandidate(
        plugin_id=manifest.plugin_id,
        capability_id=route.capability.capability_id,
        intent_name=route.intent.name,
        confidence=DETERMINISTIC_INTERCEPT_CONFIDENCE,
        match_reasons=(
            "dialog_intercept",
            f"intercept_rule:{match.rule_id}",
            f"intercept_type:{match.match_type}",
        ),
        extracted_params=match.arguments,
        missing_params=(),
        requires_confirmation=requires_confirmation,
        safety_level=safety_level,
        priority_class=route.intent.priority_class,
        route_key=route_key,
    )


def freeze_mapping(value: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Return a recursively immutable mapping suitable for route evidence."""
    if value is None:
        return MappingProxyType({})
    return MappingProxyType(
        {str(key): _freeze_value(item) for key, item in dict(value).items()}
    )


def mutable_mapping(value: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a deep mutable copy for plugin invocation boundaries."""
    if value is None:
        return {}
    return {str(key): _mutable_value(item) for key, item in dict(value).items()}


def normalise_text(value: Any, normalisation: InterceptNormalisation) -> str:
    """Return canonical text for core deterministic matching."""
    if normalisation.mode != "spoken_command":
        raise PluginInterceptionMetadataError(
            f"Unsupported normalisation '{normalisation.mode}'."
        )
    text = str(value or "").casefold().strip()
    text = re.sub(r"[^a-z0-9'_.%°\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .-?")
    for source, replacement in normalisation.replacements.items():
        text = re.sub(rf"\b{re.escape(source)}\b", replacement, text)
    return re.sub(r"\s+", " ", text).strip(" .-?")


def _parse_normalisation(raw: Mapping[str, Any]) -> InterceptNormalisation:
    """Parse core-owned normalisation configuration."""
    mode = str(raw.get("normalisation") or "spoken_command").strip()
    raw_replacements = raw.get("normalisation_replacements", {})
    if not isinstance(raw_replacements, dict):
        raise PluginInterceptionMetadataError(
            "normalisation_replacements must be a JSON object."
        )
    if len(raw_replacements) > MAX_NORMALISATION_REPLACEMENTS:
        raise PluginInterceptionMetadataError(
            "normalisation_replacements exceeds the 100-entry limit."
        )
    replacements: dict[str, str] = {}
    for source, replacement in raw_replacements.items():
        source_text = str(source or "").casefold().strip()
        replacement_text = str(replacement or "").casefold().strip()
        if not source_text or not replacement_text:
            raise PluginInterceptionMetadataError(
                "normalisation_replacements values must be non-empty strings."
            )
        if (
            len(source_text) > MAX_NORMALISATION_REPLACEMENT_CHARS
            or len(replacement_text) > MAX_NORMALISATION_REPLACEMENT_CHARS
        ):
            raise PluginInterceptionMetadataError(
                "normalisation_replacements entries exceed the 128-character limit."
            )
        replacements[source_text] = replacement_text
    return InterceptNormalisation(
        mode=mode,
        replacements=MappingProxyType(replacements),
    )


def _parse_rules(
    raw_rules: Any,
    *,
    route_lookup: Mapping[str, ManifestRoute],
) -> tuple[InterceptRule, ...]:
    """Parse and validate metadata rule objects."""
    if not isinstance(raw_rules, list):
        raise PluginInterceptionMetadataError("rules must be a JSON array.")
    if len(raw_rules) > MAX_INTERCEPT_RULES:
        raise PluginInterceptionMetadataError("rules exceeds the 100-entry limit.")
    rules: list[InterceptRule] = []
    seen_ids: set[str] = set()
    for index, raw_rule in enumerate(raw_rules):
        if not isinstance(raw_rule, dict):
            raise PluginInterceptionMetadataError(
                f"rules[{index}] must be a JSON object."
            )
        rule_id = _required_string(raw_rule.get("rule_id"), f"rules[{index}].rule_id")
        if rule_id in seen_ids:
            raise PluginInterceptionMetadataError(
                f"Duplicate interception rule_id: {rule_id}"
            )
        seen_ids.add(rule_id)
        route_id = _required_string(raw_rule.get("route_id"), f"{rule_id}.route_id")
        if route_id not in route_lookup:
            raise PluginInterceptionMetadataError(
                f"Rule '{rule_id}' references unknown route_id '{route_id}'."
            )
        match_type = _required_string(
            raw_rule.get("match_type"),
            f"{rule_id}.match_type",
        )
        if match_type not in {"exact_any", "regex"}:
            raise PluginInterceptionMetadataError(
                f"Rule '{rule_id}' uses unsupported match_type '{match_type}'."
            )
        values = _string_tuple(
            raw_rule.get("values", []),
            f"{rule_id}.values",
            max_items=MAX_EXACT_VALUES_PER_RULE,
            max_chars=MAX_EXACT_VALUE_CHARS,
        )
        patterns = _string_tuple(
            raw_rule.get("patterns", []),
            f"{rule_id}.patterns",
            max_items=MAX_REGEX_PATTERNS_PER_RULE,
            max_chars=MAX_REGEX_PATTERN_CHARS,
        )
        if match_type == "exact_any" and not values:
            raise PluginInterceptionMetadataError(
                f"Rule '{rule_id}' must define values for exact_any."
            )
        if match_type == "regex" and not patterns:
            raise PluginInterceptionMetadataError(
                f"Rule '{rule_id}' must define patterns for regex."
            )
        priority = raw_rule.get("priority", 0)
        if not isinstance(priority, int):
            raise PluginInterceptionMetadataError(
                f"Rule '{rule_id}' priority must be an integer."
            )
        arguments = raw_rule.get("arguments", {})
        if not isinstance(arguments, dict):
            raise PluginInterceptionMetadataError(
                f"Rule '{rule_id}' arguments must be a JSON object."
            )
        rules.append(
            InterceptRule(
                rule_id=rule_id,
                route_id=route_id,
                match_type=match_type,  # type: ignore[arg-type]
                priority=priority,
                values=values,
                patterns=patterns,
                arguments=freeze_mapping(arguments),
                declaration_order=index,
            )
        )
    return tuple(rules)


def _evaluate_rules(
    metadata: CompiledInterceptMetadata,
    normalised_text: str,
) -> tuple[_RawRuleMatch, ...]:
    """Return every syntactic rule match for one normalised utterance."""
    matches: list[_RawRuleMatch] = []
    for compiled in metadata.rules:
        captures = _match_compiled_rule(compiled, normalised_text)
        if captures is None:
            continue
        matches.append(
            _RawRuleMatch(
                rule=compiled.rule,
                captures=MappingProxyType(captures),
            )
        )
    return tuple(matches)


def _match_compiled_rule(
    compiled: CompiledInterceptRule,
    normalised_text: str,
) -> dict[str, str] | None:
    """Return captures for one compiled rule or ``None``."""
    if compiled.rule.match_type == "exact_any":
        return {} if normalised_text in compiled.exact_values else None
    for pattern in compiled.patterns:
        match = pattern.search(normalised_text)
        if match is None:
            continue
        return {
            key: value
            for key, value in match.groupdict().items()
            if value is not None
        }
    return None


def _select_accepted_match(
    plugin_id: str,
    accepted: list[tuple[_RawRuleMatch, Mapping[str, Any]]],
    *,
    logger: Any | None,
) -> tuple[_RawRuleMatch | None, Mapping[str, Any]]:
    """Select one accepted hook result or report local ambiguity."""
    if len(accepted) == 1:
        return accepted[0]
    first_match, first_arguments = accepted[0]
    for raw_match, arguments in accepted[1:]:
        if (
            raw_match.rule.route_id != first_match.rule.route_id
            or dict(arguments) != dict(first_arguments)
        ):
            _log_warning(
                logger,
                "Plugin dialogue interceptor ambiguity for "
                f"'{plugin_id}' between rules '{first_match.rule.rule_id}' "
                f"and '{raw_match.rule.rule_id}'.",
            )
            return None, MappingProxyType({})
    return min(
        accepted,
        key=lambda item: item[0].rule.declaration_order,
    )


def _required_string(value: Any, field_name: str) -> str:
    """Return a required non-empty string field."""
    text = str(value or "").strip()
    if not text:
        raise PluginInterceptionMetadataError(f"{field_name} must be a string.")
    return text


def _string_tuple(
    value: Any,
    field_name: str,
    *,
    max_items: int,
    max_chars: int,
) -> tuple[str, ...]:
    """Return a tuple of non-empty strings from a JSON array."""
    if value in (None, ()):
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise PluginInterceptionMetadataError(
            f"{field_name} must be an array of strings."
        )
    if len(value) > max_items:
        raise PluginInterceptionMetadataError(
            f"{field_name} exceeds the {max_items}-entry limit."
        )
    stripped = tuple(item.strip() for item in value if item.strip())
    if any(len(item) > max_chars for item in stripped):
        raise PluginInterceptionMetadataError(
            f"{field_name} contains a value exceeding {max_chars} characters."
        )
    return stripped


def _validate_safe_regex(pattern: str, *, rule_id: str) -> None:
    """Reject regex constructs outside the bounded interception subset."""
    if not pattern.startswith("^") or not pattern.endswith("$"):
        raise PluginInterceptionMetadataError(
            f"Regex for rule '{rule_id}' must be anchored with ^ and $."
        )
    if _REGEX_BACKREFERENCE.search(pattern):
        raise PluginInterceptionMetadataError(
            f"Regex for rule '{rule_id}' must not use backreferences."
        )
    if _REGEX_LOOKBEHIND.search(pattern):
        raise PluginInterceptionMetadataError(
            f"Regex for rule '{rule_id}' must not use lookbehind."
        )
    if _REGEX_NESTED_QUANTIFIER.search(pattern):
        raise PluginInterceptionMetadataError(
            f"Regex for rule '{rule_id}' contains a nested quantifier."
        )


def _freeze_value(value: Any) -> Any:
    """Return a recursively immutable representation of JSON-style values."""
    if isinstance(value, Mapping):
        return freeze_mapping(value)
    if isinstance(value, list | tuple):
        return tuple(_freeze_value(item) for item in value)
    if isinstance(value, set | frozenset):
        return frozenset(_freeze_value(item) for item in value)
    return value


def _mutable_value(value: Any) -> Any:
    """Return a recursively mutable representation for plugin invocation."""
    if isinstance(value, Mapping):
        return mutable_mapping(value)
    if isinstance(value, tuple | list):
        return [_mutable_value(item) for item in value]
    if isinstance(value, frozenset | set):
        return sorted(_mutable_value(item) for item in value)
    return value


def _log_warning(logger: Any | None, message: str) -> None:
    """Log a warning through the project logger shape when available."""
    if logger is not None and hasattr(logger, "log_warning"):
        logger.log_warning(message)
