"""Plugin execution orchestration for candidate plugins."""
# Author: Clive Bostock
# Date: 2026-04-30
# Description: Tries routed plugin candidates in order and returns the first
#   handled result.

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
import queue
import re
import threading
from typing import Any

from model.plugin_audit_adapter import PluginAuditAdapter
from model.plugin_audit_adapter import PluginAuditSession
from model.plugin_execution_policy import (
    evaluate_plugin_policy,
    plugin_policy_message,
)
from model.plugin_config import PluginConfigManager
from model.plugin_routing.models import PluginManifest
from model.plugin_routing.models import PluginRouteCandidate
from model.plugin_routing.handoff import PluginRoutingHandoff
from model.plugin_runtime import (
    PluginDataAccess,
    PluginExecutionResult,
    PluginRuntimeContext,
    PluginRuntimeError,
    instantiate_plugin,
    load_plugin_class,
)
from model.plugin_database_session import OracPluginDatabaseSessionFactory
from model.plugin_secret_vault import PluginSecretVault


_STOPWORDS = {
    "about",
    "across",
    "after",
    "again",
    "any",
    "are",
    "before",
    "can",
    "could",
    "does",
    "down",
    "for",
    "from",
    "handles",
    "into",
    "its",
    "need",
    "needs",
    "now",
    "off",
    "on",
    "please",
    "requested",
    "the",
    "then",
    "this",
    "through",
    "turn",
    "use",
    "what",
    "when",
    "where",
    "will",
    "with",
    "you",
}

_ACTION_INTENT_REQUIRED_TYPES = {
    "local_mutation",
    "external_mutation",
    "device_control",
    "privileged_system_action",
}

_ACTION_INTENT_TERMS = {
    "activate",
    "adjust",
    "brighten",
    "brightness",
    "change",
    "close",
    "control",
    "deactivate",
    "dim",
    "disable",
    "down",
    "enable",
    "execute",
    "increase",
    "launch",
    "lower",
    "make",
    "mute",
    "off",
    "on",
    "open",
    "pause",
    "play",
    "raise",
    "resume",
    "run",
    "select",
    "set",
    "skip",
    "start",
    "stop",
    "switch",
    "synchronise",
    "synchronize",
    "warm",
    "white",
    "color",
    "colour",
    "kelvin",
    "turn",
    "unmute",
    "up",
}

_FACTUAL_QUESTION_STARTERS = {
    "are",
    "did",
    "do",
    "does",
    "how",
    "is",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
}


DEFAULT_PLUGIN_EXECUTION_TIMEOUT_SECONDS = 10.0
_DECLINED = object()


@dataclass(frozen=True)
class _PluginInvocationError(Exception):
    """Wraps plugin invocation failures with the failing stage."""

    stage: str
    original: BaseException


class _PluginInvocationTimeout(TimeoutError):
    """Raised when a plugin invocation exceeds its execution budget."""


class PluginRouter:
    """Attempts execution for candidate plugins without owning discovery or indexing."""

    def __init__(
        self,
        plugin_manager,
        logger,
        config_mgr,
        context_manager,
        confirmation_broker=None,
        plugin_service_manager=None,
        plugin_db_session_factory=None,
        execution_timeout_seconds: float | None = None,
    ):
        self._plugin_manager = plugin_manager
        self._logger = logger
        self._config_mgr = config_mgr
        self._context_manager = context_manager
        self._confirmation_broker = confirmation_broker
        self._plugin_service_manager = plugin_service_manager
        self._plugin_db_session_factory = (
            plugin_db_session_factory
            or OracPluginDatabaseSessionFactory(
                config_mgr=config_mgr,
                logger=logger,
            ).create
        )
        self._execution_timeout_seconds = _resolve_execution_timeout_seconds(
            config_mgr,
            explicit_timeout=execution_timeout_seconds,
        )

    def route(
        self,
        prompt: str,
        meta: dict[str, Any] | None,
        handoff: PluginRoutingHandoff | None,
        auth_user: str,
        *,
        audit_adapter: PluginAuditAdapter | None = None,
        request_context: dict[str, Any] | None = None,
    ) -> PluginExecutionResult | None:
        """Execute the selected plugin route, or return ``None`` for fallback."""
        if handoff is None or not handoff.candidates or self._plugin_manager is None:
            return None

        meta = meta or {}
        request_context = request_context or {}

        for candidate in handoff.candidates[:1]:
            candidate_prompt = _candidate_prompt(prompt, candidate)
            manifest = self._plugin_manager.get_manifest(candidate.plugin_id)
            if manifest is None:
                self._logger.log_debug(
                    f"Plugin execution skipped because manifest '{candidate.plugin_id}' was not found."
                )
                continue
            if not manifest.entry_point:
                self._logger.log_debug(
                    f"Plugin execution skipped for '{candidate.plugin_id}' because no entry_point is defined."
                )
                continue

            policy_decision = evaluate_plugin_policy(
                manifest,
                meta=meta,
                confirmation_broker=self._confirmation_broker,
            )
            if not policy_decision.allowed:
                denial_skip_reason = self._denied_candidate_skip_reason(manifest, candidate_prompt)
                if denial_skip_reason is not None:
                    self._logger.log_debug(denial_skip_reason)
                    continue
                self._logger.log_warning(
                    "Plugin execution blocked for "
                    f"'{candidate.plugin_id}': {policy_decision.reason}"
                )
                audit_session = self._start_audit_session(
                    audit_adapter=audit_adapter,
                    request_context=request_context,
                    manifest=manifest,
                    policy_decision=policy_decision,
                    auth_user=auth_user,
                )
                self._record_policy_outcome(
                    audit_session=audit_session,
                    policy_decision=policy_decision,
                )
                self._record_confirmation_outcome(
                    audit_session=audit_session,
                    policy_decision=policy_decision,
                )
                return PluginExecutionResult(
                    plugin_id=manifest.plugin_id,
                    content=plugin_policy_message(policy_decision),
                    handled=True,
                    provenance=_with_arbitration_provenance(
                        policy_decision.provenance,
                        request_context,
                        candidate,
                    ),
                )

            audit_session = self._start_audit_session(
                audit_adapter=audit_adapter,
                request_context=request_context,
                manifest=manifest,
                policy_decision=policy_decision,
                auth_user=auth_user,
            )
            self._record_policy_outcome(
                audit_session=audit_session,
                policy_decision=policy_decision,
            )
            self._record_confirmation_outcome(
                audit_session=audit_session,
                policy_decision=policy_decision,
            )
            try:
                result = self._invoke_with_timeout(
                    lambda: self._invoke_plugin_candidate(
                        manifest=manifest,
                        prompt=candidate_prompt,
                        meta=meta,
                        auth_user=auth_user,
                        policy_decision=policy_decision,
                        audit_session=audit_session,
                    )
                )
            except _PluginInvocationTimeout:
                self._logger.log_error(
                    "Plugin execution timed out for "
                    f"'{candidate.plugin_id}' after {self._execution_timeout_seconds:.3f}s."
                )
                if audit_session is not None:
                    self._record_execution_outcome(
                        audit_session=audit_session,
                        event_type="execution_timed_out",
                        execution_status="timed_out",
                        timeout_seconds=self._execution_timeout_seconds,
                        failure_type="timeout",
                        failure_message=(
                            "Plugin execution exceeded the configured timeout "
                            f"of {self._execution_timeout_seconds:.3f} seconds."
                        ),
                        provenance_json=policy_decision.provenance,
                    )
                if not self._candidate_matches_prompt(manifest, candidate_prompt):
                    continue
                return self._failure_result(
                    manifest=manifest,
                    policy_provenance=policy_decision.provenance,
                    status="timed_out",
                    failure_type="timeout",
                    failure_message=(
                        "Plugin execution exceeded the configured timeout "
                        f"of {self._execution_timeout_seconds:.3f} seconds."
                    ),
                    timeout_seconds=self._execution_timeout_seconds,
                )
            except _PluginInvocationError as exc:
                self._log_exception(
                    "Plugin execution failed for "
                    f"'{candidate.plugin_id}' during {exc.stage} (non-fatal)",
                    exc.original,
                )
                if audit_session is not None:
                    self._record_execution_outcome(
                        audit_session=audit_session,
                        event_type="execution_failed",
                        execution_status="failed",
                        failure_type=type(exc.original).__name__,
                        failure_message=f"Plugin execution failed during {exc.stage}.",
                        provenance_json=policy_decision.provenance,
                    )
                if exc.stage not in {"can_handle", "execute"} and not self._candidate_matches_prompt(manifest, candidate_prompt):
                    continue
                return self._failure_result(
                    manifest=manifest,
                    policy_provenance=policy_decision.provenance,
                    status="failed",
                    failure_type=type(exc.original).__name__,
                    failure_message=f"Plugin execution failed during {exc.stage}.",
                )

            if result is _DECLINED:
                self._logger.log_debug(
                    f"Plugin '{candidate.plugin_id}' declined prompt after execution-time handle check."
                )
                return self._failure_result(
                    manifest=manifest,
                    policy_provenance=_with_arbitration_provenance(
                        policy_decision.provenance,
                        request_context,
                        candidate,
                    ),
                    status="failed",
                    failure_type="can_handle_declined",
                    failure_message=(
                        "The selected plugin declined the action request."
                    ),
                )

            if result is not None and result.handled:
                self._logger.log_info(f"Plugin '{candidate.plugin_id}' handled request directly.")
                return replace(
                    result,
                    provenance={
                        **_with_arbitration_provenance(
                            policy_decision.provenance,
                            request_context,
                            candidate,
                        ),
                        "status": "allowed",
                    },
                )

            return None

        self._logger.log_debug("No plugin candidate handled the request directly; falling back to conversational flow.")
        return None

    def _invoke_plugin_candidate(
        self,
        *,
        manifest: PluginManifest,
        prompt: str,
        meta: dict[str, Any],
        auth_user: str,
        policy_decision=None,
        audit_session: PluginAuditSession | None = None,
    ) -> PluginExecutionResult | object | None:
        """Load and invoke one policy-approved plugin candidate."""
        try:
            plugin_class = load_plugin_class(manifest)
        except BaseException as exc:
            raise _PluginInvocationError("load", exc) from exc

        try:
            data_access = PluginDataAccess(
                manifest=manifest,
                context_manager=self._context_manager,
                auth_user=auth_user,
                logger=self._logger,
            )
            runtime_context = PluginRuntimeContext(
                manifest=manifest,
                logger=self._logger,
                config_mgr=self._config_mgr,
                auth_user=auth_user,
                plugin_db_session_factory=self._plugin_db_session_factory,
                plugin_service_manager=self._plugin_service_manager,
                plugin_config_manager=PluginConfigManager(
                    manifest,
                    logger=self._logger,
                ),
                _secret_vault=PluginSecretVault(
                    plugin_id=manifest.plugin_id,
                    manifest=manifest,
                ),
            )
            plugin_instance = instantiate_plugin(
                plugin_class,
                logger=self._logger,
                config_mgr=self._config_mgr,
                data_access=data_access,
                runtime_context=runtime_context,
            )
        except BaseException as exc:
            raise _PluginInvocationError("instantiate", exc) from exc

        try:
            if hasattr(plugin_instance, "can_handle") and not plugin_instance.can_handle(prompt):
                self._record_execution_outcome(
                    audit_session=audit_session,
                    event_type="execution_failed",
                    execution_status="denied",
                    failure_type="can_handle_declined",
                    failure_message="Plugin declined prompt during can_handle.",
                    provenance_json=(
                        policy_decision.provenance if policy_decision is not None else None
                    ),
                )
                return _DECLINED
        except BaseException as exc:
            raise _PluginInvocationError("can_handle", exc) from exc

        self._record_execution_outcome(
            audit_session=audit_session,
            event_type="execution_started",
            execution_status="execution_started",
            provenance_json=policy_decision.provenance if policy_decision is not None else None,
        )

        try:
            result = plugin_instance.execute(prompt, meta)
        except BaseException as exc:
            self._record_execution_outcome(
                audit_session=audit_session,
                event_type="execution_failed",
                execution_status="failed",
                failure_type=type(exc).__name__,
                failure_message="Plugin execution failed during execute.",
                provenance_json=policy_decision.provenance if policy_decision is not None else None,
            )
            raise _PluginInvocationError("execute", exc) from exc

        if result is not None and result.handled:
            self._record_execution_outcome(
                audit_session=audit_session,
                event_type="execution_completed",
                execution_status="completed",
                provenance_json=policy_decision.provenance if policy_decision is not None else None,
            )
        return result

    def _invoke_with_timeout(self, func):
        """Run plugin invocation with a bounded wait in a daemon worker thread."""
        timeout_seconds = self._execution_timeout_seconds
        if timeout_seconds <= 0:
            return func()

        results: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

        def _target() -> None:
            try:
                results.put(("ok", func()), block=False)
            except BaseException as exc:
                results.put(("error", exc), block=False)

        thread = threading.Thread(
            target=_target,
            name="orac-plugin-execution",
            daemon=True,
        )
        thread.start()
        thread.join(timeout=timeout_seconds)
        if thread.is_alive():
            return self._raise_timeout()

        try:
            status, payload = results.get_nowait()
        except queue.Empty as exc:
            raise _PluginInvocationError(
                "execute",
                PluginRuntimeError("Plugin worker ended without returning a result."),
            ) from exc

        if status == "error":
            raise payload
        return payload

    @staticmethod
    def _raise_timeout() -> None:
        """Raise timeout from an expression position."""
        raise _PluginInvocationTimeout()

    @staticmethod
    def _failure_result(
        *,
        manifest: PluginManifest,
        policy_provenance: dict[str, Any],
        status: str,
        failure_type: str,
        failure_message: str,
        timeout_seconds: float | None = None,
    ) -> PluginExecutionResult:
        """Build a handled plugin failure result with core-owned provenance."""
        provenance = {
            **policy_provenance,
            "status": status,
            "policy_decision": policy_provenance.get("status"),
            "failure_type": failure_type,
            "failure_message": failure_message,
        }
        if timeout_seconds is not None:
            provenance["timeout_seconds"] = timeout_seconds

        if status == "timed_out":
            content = f"{manifest.name} timed out before completing the request."
        else:
            content = f"{manifest.name} could not complete the request."

        return PluginExecutionResult(
            plugin_id=manifest.plugin_id,
            content=content,
            handled=True,
            provenance=provenance,
        )

    def _log_exception(self, prefix: str, exc: BaseException) -> None:
        self._logger.log_error(f"{prefix}: {exc}")

    def _start_audit_session(
        self,
        *,
        audit_adapter: PluginAuditAdapter | None,
        request_context: dict[str, Any],
        manifest: PluginManifest,
        policy_decision,
        auth_user: str,
    ) -> PluginAuditSession | None:
        """Create an audit session only when an adapter is configured."""
        if audit_adapter is None:
            return None
        return audit_adapter.create_session(
            provenance=policy_decision.provenance,
            request_context=self._request_audit_context(
                request_context=request_context,
                manifest=manifest,
                auth_user=auth_user,
            ),
            policy_decision=policy_decision.status,
        )

    def _record_policy_outcome(
        self,
        *,
        audit_session: PluginAuditSession | None,
        policy_decision,
    ) -> None:
        """Persist a policy decision when audit is enabled."""
        if audit_session is None:
            return
        audit_session.record_policy_decision(
            policy_decision=policy_decision.status,
            policy_reason=policy_decision.reason,
            event_message=policy_decision.reason,
            provenance_json=policy_decision.provenance,
        )

    def _record_confirmation_outcome(
        self,
        *,
        audit_session: PluginAuditSession | None,
        policy_decision,
    ) -> None:
        """Persist confirmation lifecycle events when the policy supplies them."""
        if audit_session is None:
            return
        confirmation = policy_decision.provenance.get("confirmation")
        if isinstance(confirmation, dict) and confirmation.get("confirmation_id"):
            status = str(confirmation.get("status") or "").strip() or None
            if status == "trusted" or confirmation.get("trusted") is True:
                event_type = "confirmation_accepted"
                confirmation_status = "accepted"
            else:
                event_type = self._confirmation_event_type(status)
                confirmation_status = status
            audit_session.record_confirmation_event(
                event_type=event_type,
                confirmation_id=str(confirmation.get("confirmation_id") or "").strip() or None,
                confirmation_status=confirmation_status,
                event_message=str(confirmation.get("reason") or policy_decision.reason or "").strip() or None,
                event_payload_json=policy_decision.provenance,
            )
        confirmation_request = policy_decision.provenance.get("confirmation_request")
        if isinstance(confirmation_request, dict) and confirmation_request.get("confirmation_id"):
            audit_session.record_confirmation_event(
                event_type="confirmation_issued",
                confirmation_id=str(confirmation_request.get("confirmation_id") or "").strip() or None,
                confirmation_status="issued",
                event_message=policy_decision.reason,
                event_payload_json=confirmation_request,
            )

    def _record_execution_outcome(
        self,
        *,
        audit_session: PluginAuditSession | None,
        event_type: str,
        execution_status: str,
        timeout_seconds: float | None = None,
        failure_type: str | None = None,
        failure_message: str | None = None,
        provenance_json: dict[str, Any] | None = None,
    ) -> None:
        """Persist an execution lifecycle event when audit is enabled."""
        if audit_session is None:
            return
        audit_session.record_execution_event(
            event_type=event_type,
            execution_status=execution_status,
            timeout_seconds=timeout_seconds,
            failure_type=failure_type,
            failure_message=failure_message,
            provenance_json=provenance_json,
        )

    @staticmethod
    def _request_audit_context(
        *,
        request_context: dict[str, Any] | None,
        manifest: PluginManifest,
        auth_user: str,
    ) -> dict[str, Any]:
        """Return a minimal audit context for the current plugin attempt."""
        context = dict(request_context or {})
        context.setdefault("plugin_id", manifest.plugin_id)
        context.setdefault("plugin_name", manifest.name)
        context.setdefault("action_type", manifest.execution_policy.action_type if manifest.execution_policy else None)
        context.setdefault("user_id", context.get("user_id"))
        if not context.get("request_id") and context.get("req_id"):
            context["request_id"] = context.get("req_id")
        if not context.get("correlation_id"):
            context["correlation_id"] = context.get("request_id")
        if not context.get("turn_id") and context.get("request_id"):
            context["turn_id"] = context.get("request_id")
        context["auth_user"] = auth_user
        return context

    @staticmethod
    def _confirmation_event_type(status: str | None) -> str:
        """Map a confirmation status to a lifecycle event name."""
        if status == "replayed":
            return "confirmation_replay_rejected"
        if status == "expired":
            return "confirmation_expired"
        if status == "mismatched":
            return "confirmation_mismatched"
        if status in {"missing", "rejected"}:
            return "confirmation_rejected"
        return "confirmation_accepted"

    @staticmethod
    def _candidate_matches_prompt(manifest: PluginManifest, prompt: str) -> bool:
        """Return whether a denied candidate has a manifest-level prompt match.

        This no-import guard prevents weak vector-search false positives from
        becoming user-visible policy denials while preserving fail-closed
        behaviour for prompts that mention manifest-declared plugin terms.
        """
        prompt_tokens = _significant_tokens(prompt)
        if not prompt_tokens:
            return False

        manifest_text = " ".join(
            [
                manifest.plugin_id,
                manifest.name,
                manifest.description,
                " ".join(manifest.capabilities),
                " ".join(manifest.entitlements),
                " ".join(manifest.entities),
                " ".join(manifest.examples),
            ]
        )
        return bool(prompt_tokens.intersection(_significant_tokens(manifest_text)))

    @staticmethod
    def _denied_candidate_skip_reason(manifest: PluginManifest, prompt: str) -> str | None:
        """Return the reason a denied candidate should not be user-visible."""
        if not PluginRouter._candidate_matches_prompt(manifest, prompt):
            return (
                "Plugin execution denial skipped for "
                f"'{manifest.plugin_id}' because the prompt did not "
                "match manifest-declared routing terms."
            )

        action_type = (
            manifest.execution_policy.action_type
            if manifest.execution_policy is not None
            else None
        )
        if action_type in _ACTION_INTENT_REQUIRED_TYPES and not _has_action_intent(prompt):
            return (
                "Plugin execution denial skipped for "
                f"'{manifest.plugin_id}' because the prompt matched manifest terms "
                "but did not contain an explicit action intent."
            )

        return None

    @staticmethod
    def _declined_mutation_requires_failure(
        manifest: PluginManifest,
        prompt: str,
    ) -> bool:
        """Return whether a declined action must not fall through to the LLM."""
        action_type = (
            manifest.execution_policy.action_type
            if manifest.execution_policy is not None
            else None
        )
        return (
            action_type in _ACTION_INTENT_REQUIRED_TYPES
            and _has_action_intent(prompt)
            and PluginRouter._candidate_matches_prompt(manifest, prompt)
        )


def _significant_tokens(text: str) -> set[str]:
    """Return normalized non-trivial words for manifest-level routing checks."""
    tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", str(text or "").lower())
        if len(token) >= 3 and token not in _STOPWORDS
    }
    expanded = set(tokens)
    for token in tokens:
        if token.endswith("ies") and len(token) > 4:
            expanded.add(f"{token[:-3]}y")
        elif token.endswith("s") and len(token) > 3:
            expanded.add(token[:-1])
    return expanded


def _has_action_intent(text: str) -> bool:
    """Return whether text contains an explicit command-style action verb."""
    ordered_tokens = re.findall(r"[a-z0-9]+", str(text or "").lower())
    if ordered_tokens and ordered_tokens[0] in _FACTUAL_QUESTION_STARTERS:
        return False

    if ordered_tokens == ["sink", "devices"]:
        return True

    tokens = set(ordered_tokens)
    return bool(tokens.intersection(_ACTION_INTENT_TERMS))


def _candidate_prompt(prompt: str, candidate: Any) -> str:
    """Return routed prompt text for an explicitly addressed selected candidate."""
    extracted = getattr(candidate, "extracted_params", None)
    if isinstance(extracted, dict):
        routed_prompt = str(extracted.get("routed_prompt") or "").strip()
        if routed_prompt:
            return routed_prompt
    return prompt


def _with_arbitration_provenance(
    provenance: dict[str, Any],
    request_context: dict[str, Any],
    candidate: Any,
) -> dict[str, Any]:
    """Attach core arbitration details to plugin execution provenance."""
    merged = dict(provenance)
    arbitration = request_context.get("arbitration")
    if isinstance(arbitration, dict):
        merged["arbitration"] = arbitration
    if isinstance(candidate, PluginRouteCandidate):
        merged["selected_capability_id"] = candidate.capability_id
        merged["selected_intent_name"] = candidate.intent_name
        merged["route_confidence"] = candidate.confidence
        merged["route_match_reasons"] = tuple(candidate.match_reasons)
    return merged


def _resolve_execution_timeout_seconds(
    config_mgr: Any,
    *,
    explicit_timeout: float | None,
) -> float:
    """Return configured plugin execution timeout seconds."""
    if explicit_timeout is not None:
        return max(0.0, float(explicit_timeout))

    config_value = getattr(config_mgr, "config_value", None)
    if callable(config_value):
        try:
            raw_timeout = config_value(
                section="plugins",
                key="execution_timeout_seconds",
                default=str(DEFAULT_PLUGIN_EXECUTION_TIMEOUT_SECONDS),
            )
            return max(0.0, float(raw_timeout))
        except (TypeError, ValueError):
            return DEFAULT_PLUGIN_EXECUTION_TIMEOUT_SECONDS

    return DEFAULT_PLUGIN_EXECUTION_TIMEOUT_SECONDS
