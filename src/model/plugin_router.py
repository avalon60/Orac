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

from model.plugin_execution_policy import (
    evaluate_plugin_policy,
    plugin_policy_message,
)
from model.plugin_routing.models import PluginManifest
from model.plugin_routing.handoff import PluginRoutingHandoff
from model.plugin_runtime import (
    PluginDataAccess,
    PluginExecutionResult,
    PluginRuntimeError,
    instantiate_plugin,
    load_plugin_class,
)


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
        execution_timeout_seconds: float | None = None,
    ):
        self._plugin_manager = plugin_manager
        self._logger = logger
        self._config_mgr = config_mgr
        self._context_manager = context_manager
        self._confirmation_broker = confirmation_broker
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
    ) -> PluginExecutionResult | None:
        """Returns the first successful plugin execution result, or None."""
        if handoff is None or not handoff.candidates or self._plugin_manager is None:
            return None

        meta = meta or {}

        for candidate in handoff.candidates:
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
                if not self._candidate_matches_prompt(manifest, prompt):
                    self._logger.log_debug(
                        "Plugin execution denial skipped for "
                        f"'{candidate.plugin_id}' because the prompt did not "
                        "match manifest-declared routing terms."
                    )
                    continue
                self._logger.log_warning(
                    "Plugin execution blocked for "
                    f"'{candidate.plugin_id}': {policy_decision.reason}"
                )
                return PluginExecutionResult(
                    plugin_id=manifest.plugin_id,
                    content=plugin_policy_message(policy_decision),
                    handled=True,
                    provenance=policy_decision.provenance,
                )

            try:
                result = self._invoke_with_timeout(
                    lambda: self._invoke_plugin_candidate(
                        manifest=manifest,
                        prompt=prompt,
                        meta=meta,
                        auth_user=auth_user,
                    )
                )
            except _PluginInvocationTimeout:
                self._logger.log_error(
                    "Plugin execution timed out for "
                    f"'{candidate.plugin_id}' after {self._execution_timeout_seconds:.3f}s."
                )
                if not self._candidate_matches_prompt(manifest, prompt):
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
                if exc.stage not in {"can_handle", "execute"} and not self._candidate_matches_prompt(manifest, prompt):
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
                continue

            if result is not None and result.handled:
                self._logger.log_info(f"Plugin '{candidate.plugin_id}' handled request directly.")
                return replace(
                    result,
                    provenance={
                        **policy_decision.provenance,
                        "status": "allowed",
                    },
                )

        self._logger.log_debug("No plugin candidate handled the request directly; falling back to conversational flow.")
        return None

    def _invoke_plugin_candidate(
        self,
        *,
        manifest: PluginManifest,
        prompt: str,
        meta: dict[str, Any],
        auth_user: str,
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
            plugin_instance = instantiate_plugin(
                plugin_class,
                logger=self._logger,
                config_mgr=self._config_mgr,
                data_access=data_access,
            )
        except BaseException as exc:
            raise _PluginInvocationError("instantiate", exc) from exc

        try:
            if hasattr(plugin_instance, "can_handle") and not plugin_instance.can_handle(prompt):
                return _DECLINED
        except BaseException as exc:
            raise _PluginInvocationError("can_handle", exc) from exc

        try:
            return plugin_instance.execute(prompt, meta)
        except BaseException as exc:
            raise _PluginInvocationError("execute", exc) from exc

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
