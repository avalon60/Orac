"""Core-owned arbitration for plugin route candidates."""
# Author: Clive Bostock
# Date: 19-Jun-2026
# Description: Decides whether plugin route candidates own a user turn.

from __future__ import annotations

from dataclasses import replace
import re
from typing import Any

from model.plugin_routing.models import (
    ArbitrationDecision,
    PluginCandidate,
    PluginManifest,
    PluginRouteCandidate,
)


HIGH_CONFIDENCE_THRESHOLD = 0.85
PLAUSIBLE_CONFIDENCE_THRESHOLD = 0.60
CLOSE_TIE_DELTA = 0.08

_ACTION_SAFETY_LEVELS = {
    "local_mutation",
    "external_mutation",
    "device_control",
    "privileged_system_action",
}

_ACTION_TERMS = {
    "activate",
    "add",
    "adjust",
    "analyse",
    "analyze",
    "ask",
    "brighten",
    "cancel",
    "change",
    "close",
    "control",
    "create",
    "deactivate",
    "delete",
    "dim",
    "disable",
    "enable",
    "execute",
    "increase",
    "lower",
    "make",
    "mute",
    "off",
    "on",
    "open",
    "pause",
    "play",
    "raise",
    "repeat",
    "resume",
    "run",
    "set",
    "shutdown",
    "start",
    "stop",
    "switch",
    "sync",
    "synchronise",
    "synchronize",
    "tell",
    "turn",
    "unmute",
    "use",
}

_QUESTION_STARTERS = {
    "are",
    "can",
    "did",
    "do",
    "does",
    "how",
    "is",
    "should",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
}

_DISCUSSION_TERMS = {
    "architecture",
    "design",
    "doc",
    "docs",
    "document",
    "documentation",
    "example",
    "phrase",
    "problem",
    "route",
    "routing",
    "plugin",
    "plugins",
    "prompt",
    "sentence",
    "write",
}

_CORE_COMMAND_PHRASES = {
    ("cancel",),
    ("cancel", "that"),
    ("go", "idle"),
    ("go", "to", "idle"),
    ("go", "to", "sleep"),
    ("mute",),
    ("repeat",),
    ("shut", "down"),
    ("shutdown",),
    ("stop",),
    ("unmute",),
}

_POLITE_TOKENS = {"please", "orac"}


class PluginArbiter:
    """Resolve contention between plugin route candidates in Orac core."""

    def __init__(
        self,
        *,
        plugin_manager: Any | None = None,
        logger: Any | None = None,
        high_confidence_threshold: float = HIGH_CONFIDENCE_THRESHOLD,
        plausible_confidence_threshold: float = PLAUSIBLE_CONFIDENCE_THRESHOLD,
        close_tie_delta: float = CLOSE_TIE_DELTA,
    ) -> None:
        """Initialise the arbiter.

        Args:
            plugin_manager: Optional plugin manager used for explicit-address
                name resolution.
            logger: Optional project logger.
            high_confidence_threshold: Score required for direct ownership.
            plausible_confidence_threshold: Score required for clarification.
            close_tie_delta: Maximum score gap treated as an ambiguous tie.
        """
        self._plugin_manager = plugin_manager
        self._logger = logger
        self._high = high_confidence_threshold
        self._plausible = plausible_confidence_threshold
        self._tie_delta = close_tie_delta

    def arbitrate(
        self,
        *,
        utterance: str,
        candidates: tuple[PluginRouteCandidate | PluginCandidate, ...],
        pending_context: dict[str, Any] | None = None,
    ) -> ArbitrationDecision:
        """Return the core-owned routing decision for one user utterance."""
        route_candidates = tuple(self._coerce_candidate(candidate) for candidate in candidates)
        if _is_core_reserved_command(utterance):
            return self._decision(
                "core_command",
                None,
                route_candidates,
                "core_reserved_command",
                None,
                utterance,
            )

        pending_decision = self._pending_context_decision(
            utterance=utterance,
            candidates=route_candidates,
            pending_context=pending_context,
        )
        if pending_decision is not None:
            return pending_decision

        addressed_plugin_ids, addressed_text, ambiguous_name = self._explicit_plugin_address(
            utterance
        )
        if ambiguous_name:
            return self._decision(
                "clarify",
                None,
                route_candidates,
                "explicit_plugin_name_ambiguous",
                "Which plugin do you mean?",
                utterance,
            )

        if addressed_plugin_ids:
            route_candidates = tuple(
                candidate
                for candidate in route_candidates
                if candidate.plugin_id in addressed_plugin_ids
            )
            if addressed_text:
                route_candidates = tuple(
                    replace(
                        candidate,
                        extracted_params={
                            **(candidate.extracted_params or {}),
                            "routed_prompt": addressed_text,
                        },
                        match_reasons=(
                            *candidate.match_reasons,
                            "explicit_plugin_addressing",
                        ),
                    )
                    for candidate in route_candidates
                )
            if not route_candidates:
                plugin_name = ", ".join(sorted(addressed_plugin_ids))
                return self._decision(
                    "clarify",
                    None,
                    (),
                    "explicit_plugin_lacks_matching_capability",
                    f"{plugin_name} does not appear to have a matching capability for that request.",
                    utterance,
                )
            return self._arbitrate_candidates(
                utterance=addressed_text or utterance,
                candidates=route_candidates,
                explicit=True,
            )

        return self._arbitrate_candidates(
            utterance=utterance,
            candidates=route_candidates,
            explicit=False,
        )

    def _arbitrate_candidates(
        self,
        *,
        utterance: str,
        candidates: tuple[PluginRouteCandidate, ...],
        explicit: bool,
    ) -> ArbitrationDecision:
        """Apply confidence, directive, and ambiguity rules."""
        if not candidates:
            return self._decision(
                "llm_fallback",
                None,
                (),
                "no_plugin_candidates",
                None,
                utterance,
            )

        if _looks_like_quoted_or_discussion_context(utterance):
            gated: tuple[PluginRouteCandidate, ...] = ()
        else:
            gated = tuple(
                candidate
                for candidate in candidates
                if explicit or _candidate_passes_directive_gate(utterance, candidate)
            )
        if not gated:
            return self._decision(
                "llm_fallback",
                None,
                candidates,
                "no_directive_for_plugin_action",
                None,
                utterance,
            )

        ordered = tuple(
            sorted(gated, key=lambda candidate: candidate.confidence, reverse=True)
        )
        high = tuple(
            candidate for candidate in ordered if candidate.confidence >= self._high
        )
        plausible = tuple(
            candidate
            for candidate in ordered
            if candidate.confidence >= self._plausible
        )

        if len(high) == 1 and not self._has_close_tie(high[0], ordered[1:]):
            return self._selected_decision(
                high[0],
                ordered,
                "clear_high_confidence_candidate",
                utterance,
            )
        if len(high) > 1:
            return self._decision(
                "clarify",
                None,
                ordered,
                "multiple_high_confidence_candidates",
                self._clarification_for(ordered),
                utterance,
            )
        if len(plausible) == 1 and explicit:
            return self._selected_decision(
                plausible[0],
                ordered,
                "explicit_plausible_candidate",
                utterance,
            )
        if plausible:
            return self._decision(
                "clarify",
                None,
                ordered,
                "weak_or_ambiguous_plugin_candidates",
                self._clarification_for(plausible),
                utterance,
            )
        return self._decision(
            "llm_fallback",
            None,
            ordered,
            "plugin_candidates_below_threshold",
            None,
            utterance,
        )

    def _pending_context_decision(
        self,
        *,
        utterance: str,
        candidates: tuple[PluginRouteCandidate, ...],
        pending_context: dict[str, Any] | None,
    ) -> ArbitrationDecision | None:
        """Return a selected pending-context decision for short replies."""
        if not pending_context:
            return None
        plugin_id = str(pending_context.get("plugin_id") or "").strip()
        capability_id = str(pending_context.get("capability_id") or "").strip()
        intent_name = str(pending_context.get("intent_name") or "").strip()
        if not plugin_id or len(_tokens(utterance)) > 5:
            return None
        for candidate in candidates:
            if (
                candidate.plugin_id == plugin_id
                and (not capability_id or candidate.capability_id == capability_id)
                and (not intent_name or candidate.intent_name == intent_name)
            ):
                return self._selected_decision(
                    candidate,
                    candidates,
                    "pending_plugin_context",
                    utterance,
                )
        manifest = self._manifest(plugin_id)
        if manifest is None:
            return None
        fallback = PluginRouteCandidate(
            plugin_id=plugin_id,
            capability_id=capability_id or (manifest.capabilities[0] if manifest.capabilities else ""),
            intent_name=intent_name or "pending_context",
            confidence=1.0,
            match_reasons=("pending_plugin_context",),
            extracted_params={"routed_prompt": utterance},
            requires_confirmation=bool(
                manifest.execution_policy.requires_confirmation
                if manifest.execution_policy is not None
                else False
            ),
            safety_level=str(
                manifest.execution_policy.action_type
                if manifest.execution_policy is not None
                else "informational_read_only"
            ),
        )
        return self._selected_decision(fallback, (fallback,), "pending_plugin_context", utterance)

    def _explicit_plugin_address(
        self,
        utterance: str,
    ) -> tuple[set[str], str | None, bool]:
        """Return addressed plugin ids, stripped command text, and ambiguity."""
        manifests = self._known_manifests()
        if not manifests:
            return set(), None, False
        lowered = _normalise_space(utterance).lower()
        matches: list[tuple[PluginManifest, str]] = []
        for manifest in manifests:
            names = {
                manifest.plugin_id.replace("_", " "),
                manifest.name.lower(),
                f"{manifest.name.lower()} plugin",
                f"{manifest.plugin_id.replace('_', ' ')} plugin",
            }
            for name in names:
                if re.search(rf"\b{re.escape(name)}\b", lowered):
                    matches.append((manifest, name))
                    break
        if not matches:
            return set(), None, False
        explicit_verbs = ("ask", "use", "tell")
        if not any(re.search(rf"\b{verb}\b", lowered) for verb in explicit_verbs):
            return set(), None, False
        plugin_ids = {manifest.plugin_id for manifest, _ in matches}
        if len(plugin_ids) > 1:
            return plugin_ids, None, True
        manifest, matched_name = matches[0]
        stripped = _strip_explicit_plugin_prefix(utterance, matched_name)
        return {manifest.plugin_id}, stripped, False

    def _known_manifests(self) -> tuple[PluginManifest, ...]:
        """Return manifests known to the plugin manager."""
        manager = self._plugin_manager
        if manager is None:
            return ()
        route_records = getattr(manager, "route_records", None)
        if callable(route_records):
            return tuple({record[0].plugin_id: record[0] for record in route_records()}.values())
        manifests = getattr(manager, "_manifests", {})
        if isinstance(manifests, dict):
            return tuple(manifests.values())
        return ()

    def _manifest(self, plugin_id: str) -> PluginManifest | None:
        manager = self._plugin_manager
        if manager is None:
            return None
        getter = getattr(manager, "get_manifest", None)
        if callable(getter):
            return getter(plugin_id)
        return None

    def _selected_decision(
        self,
        candidate: PluginRouteCandidate,
        candidates: tuple[PluginRouteCandidate, ...],
        reason: str,
        utterance: str,
    ) -> ArbitrationDecision:
        decision_type = "confirm" if candidate.requires_confirmation else "execute_plugin"
        return self._decision(decision_type, candidate, candidates, reason, None, utterance)

    def _decision(
        self,
        decision_type: str,
        selected: PluginRouteCandidate | None,
        candidates: tuple[PluginRouteCandidate, ...],
        reason: str,
        clarification_prompt: str | None,
        utterance: str,
    ) -> ArbitrationDecision:
        """Build and log one arbitration decision."""
        decision = ArbitrationDecision(
            decision_type=decision_type,  # type: ignore[arg-type]
            selected_plugin_id=selected.plugin_id if selected else None,
            selected_capability_id=selected.capability_id if selected else None,
            selected_intent_name=selected.intent_name if selected else None,
            candidates=candidates,
            reason=reason,
            clarification_prompt=clarification_prompt,
            utterance=_redact_sensitive_text(utterance),
        )
        self._log_decision(decision)
        return decision

    def _log_decision(self, decision: ArbitrationDecision) -> None:
        if self._logger is None:
            return
        summary = ", ".join(
            f"{candidate.plugin_id}/{candidate.capability_id}/{candidate.intent_name}="
            f"{candidate.confidence:.4f}"
            for candidate in decision.candidates
        )
        self._logger.log_debug(
            "Plugin arbitration decision: "
            f"type={decision.decision_type} "
            f"selected={decision.selected_plugin_id or '-'} "
            f"reason={decision.reason} "
            f"utterance={decision.utterance!r} "
            f"candidates=[{summary}]"
        )

    @staticmethod
    def _has_close_tie(
        selected: PluginRouteCandidate,
        remaining: tuple[PluginRouteCandidate, ...],
    ) -> bool:
        if not remaining:
            return False
        return selected.confidence - remaining[0].confidence <= CLOSE_TIE_DELTA

    @staticmethod
    def _clarification_for(candidates: tuple[PluginRouteCandidate, ...]) -> str:
        plugin_names = sorted({candidate.plugin_id for candidate in candidates})
        if len(plugin_names) <= 1:
            return "Which plugin action do you want me to use?"
        return "Which plugin should handle that: " + ", ".join(plugin_names) + "?"

    @staticmethod
    def _coerce_candidate(
        candidate: PluginRouteCandidate | PluginCandidate,
    ) -> PluginRouteCandidate:
        if isinstance(candidate, PluginRouteCandidate):
            return candidate
        return PluginRouteCandidate(
            plugin_id=candidate.plugin_id,
            capability_id=getattr(candidate, "capability_id", "") or "",
            intent_name=getattr(candidate, "intent_name", "") or "default",
            confidence=float(candidate.score),
            match_reasons=("legacy_plugin_candidate",),
            extracted_params={},
            route_key=getattr(candidate, "route_key", "") or "",
        )


def _candidate_passes_directive_gate(
    utterance: str,
    candidate: PluginRouteCandidate,
) -> bool:
    """Return whether deterministic action/directive signals allow ownership."""
    safety_level = str(candidate.safety_level or "").strip()
    tokens = _tokens(utterance)
    if safety_level in _ACTION_SAFETY_LEVELS:
        return _has_action_directive(tokens)
    if tokens and tokens[0] in _QUESTION_STARTERS:
        return True
    return _has_action_directive(tokens)


def _is_core_reserved_command(utterance: str) -> bool:
    """Return whether text is an exact or near-exact Orac control command."""
    tokens = tuple(token for token in _tokens(utterance) if token not in _POLITE_TOKENS)
    if tokens in _CORE_COMMAND_PHRASES:
        return True
    if len(tokens) <= 3 and tokens[:1] in {(phrase[0],) for phrase in _CORE_COMMAND_PHRASES}:
        return tokens in _CORE_COMMAND_PHRASES
    return False


def _has_action_directive(tokens: tuple[str, ...]) -> bool:
    """Return whether tokenized text contains a command-style directive."""
    if not tokens:
        return False
    if tokens[0] in _QUESTION_STARTERS:
        return False
    if tokens == ("sink", "devices"):
        return True
    return bool(set(tokens).intersection(_ACTION_TERMS))


def _looks_like_quoted_or_discussion_context(utterance: str) -> bool:
    """Return whether the utterance discusses text rather than issuing it."""
    lowered = _normalise_space(utterance).lower()
    tokens = set(_tokens(lowered))
    if tokens.intersection(_DISCUSSION_TERMS):
        if re.search(r"['\"].+['\"]", utterance):
            return True
        if {"example", "problem", "design", "document", "documentation"}.intersection(tokens):
            return True
    if re.match(r"^(document|write|quote|record)\b", lowered):
        return True
    return False


def _strip_explicit_plugin_prefix(utterance: str, plugin_name: str) -> str:
    """Remove a simple explicit plugin-addressing prefix from the utterance."""
    text = _normalise_space(utterance)
    pattern = re.compile(
        rf"^(?:please\s+)?(?:ask|use|tell)\s+(?:the\s+)?"
        rf"{re.escape(plugin_name)}\s*(?:plugin)?\s*(?:to\s+)?",
        flags=re.IGNORECASE,
    )
    stripped = pattern.sub("", text).strip()
    return stripped or text


def _tokens(text: str) -> tuple[str, ...]:
    """Return normalized alphanumeric tokens."""
    return tuple(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def _normalise_space(text: str) -> str:
    """Collapse whitespace for deterministic matching."""
    return " ".join(str(text or "").strip().split())


def _redact_sensitive_text(text: str) -> str:
    """Redact common secret-bearing fragments from arbitration audit text."""
    value = str(text or "")
    patterns = (
        re.compile(r"(?i)\b(bearer)\s+[a-z0-9._~+/=-]{8,}"),
        re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|secret)\s*[:=]\s*['\"]?[^'\"\s,;]+"),
    )
    redacted = value
    for pattern in patterns:
        redacted = pattern.sub(lambda match: f"{match.group(1)} [REDACTED]", redacted)
    return redacted
