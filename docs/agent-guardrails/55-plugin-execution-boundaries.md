# Plugin Execution Boundaries

This note records the intended ownership boundaries for Orac plugin execution.
It is deliberately narrower than a full plugin SDK.

## Intended Flow

1. `PluginDiscovery` reads and validates top-level plugin manifests.
   Discovery must not import plugin implementation code.
2. `PluginManager` builds route-intent candidates from manifest metadata and
   prepared core-owned dialogue interceptors. Embeddings are a ranking signal,
   not an authority layer.
3. `PluginArbiter` resolves contention between route candidates. It protects
   core-reserved commands, honours explicit plugin addressing, applies
   directive/action gating, and asks for clarification on ambiguous matches.
4. `PluginRouter` receives at most one arbitration-selected candidate, resolves
   that candidate's manifest, and asks Orac-owned policy code to evaluate the
   manifest execution policy.
5. `plugin_execution_policy.evaluate_plugin_policy` decides whether execution is
   allowed, denied, or requires confirmation. Plugin code is not imported before
   this decision.
6. Only allowed plugins are imported and invoked.
7. For migrated interceptor plugins, `PluginRouter` passes the selected route
   in `meta["plugin_route"]` and bypasses legacy `can_handle()` ownership
   checks during normal routing.
8. Orac-owned code creates provenance for plugin results. Plugin code may return
   content, but it does not author final provenance or policy status.
9. `Orac` carries provenance into response metadata and assistant-turn
   persistence metadata.

## Ownership Rules

- Manifests declare action risk through `execution.action_type`,
  `requires_confirmation`, `allowed_by_default`, capabilities, entitlements, and
  optional scaffold metadata.
- Plugin discovery owns manifest validation only.
- Routing owns candidate discovery only. Route candidates are not plugin claims.
- Interception metadata owns dialogue matching only. Manifest routes own the
  executable capability and intent selected by a `route_id`.
- Core arbitration owns the decision about whether any plugin owns a turn.
- Orac core owns policy, confirmation, provenance, persistence, and final
  response metadata.
- `InterceptMatch` and `PluginRouteCandidate` arguments must remain immutable
  through matching and arbitration. Convert to a mutable dictionary only at the
  final plugin invocation boundary.
- Plugin implementation code must never make the final allow/deny decision for
  its own execution.
- Plugin implementation code must not become the final arbiter through
  first-match, registration-order, filesystem-order, or install-order fallback.
- The LLM may help interpret user intent, but it must not authorize device
  control, local mutation, external mutation, or privileged/system actions.

## Arbitration Rules

Core-reserved commands such as exact or near-exact stop, cancel, mute, repeat,
go idle, and shutdown requests must not be intercepted by plugins. Object-level
commands such as "stop the lounge speaker" are not core commands merely because
they contain a reserved verb.

Explicit plugin addressing, such as "Ask Home Assistant to turn on the lounge
lamp", restricts routing to the named plugin. If the named plugin is ambiguous
or does not expose a matching declared capability, Orac asks for clarification
or returns a graceful failure instead of trying another plugin.

Route-intent embeddings are shortlist and ranking inputs only. The arbiter must
still apply deterministic directive/action gating, quoted-example detection,
plugin-name discussion detection, confirmation requirements, and ambiguity
checks before execution.

For migrated plugins that declare `routing.interceptor`, normal routing must
not call `can_handle()`. The selected manifest route is passed to execution as:

```python
meta["plugin_route"] = {
    "plugin_id": candidate.plugin_id,
    "capability_id": candidate.capability_id,
    "intent_name": candidate.intent_name,
    "arguments": dict(candidate.extracted_params or {}),
    "match_reasons": list(candidate.match_reasons),
}
```

Temporary compatibility `can_handle()` methods may remain while old callers are
retired, but they must not create a second route candidate or run an independent
parser during migrated routing. For legacy plugins without an interceptor, if a
selected plugin later declines through its implementation-level `can_handle`
check, that rejection is final for the turn. Orac must not try the next
candidate as a fallback.

## Fail-Closed Cases

The following outcomes must not import or execute plugin code:

- denied actions
- scaffold or experimental plugins
- unknown action types
- actions requiring confirmation when no trusted confirmation has been provided

Scaffold denial overrides request metadata, including metadata that claims the
action was confirmed or explicitly allowed.

## Confirmation Status

`PluginConfirmationBroker` is the Orac-owned seam for risky plugin action
confirmation. It creates confirmation requests, assigns confirmation ids,
records plugin/action/capability metadata, applies expiry, and consumes
confirmed requests so they cannot be replayed.

Request metadata is not a trusted authority. Legacy
`meta.plugin_policy.confirmed` and `meta.plugin_policy.allow_risky_actions`
claims are ignored for final authorization. A caller may supply
`meta.plugin_confirmation.confirmation_id`, but policy code trusts it only when
the broker issued it, it has been explicitly confirmed, it has not expired, it
has not already been consumed, and it matches the current plugin action.

Confirmation-required policy results include a `confirmation_request`
provenance block when a broker is available. That block is the future UI/API
handoff point for a confirmation workflow. The current broker is intentionally
in-memory and does not yet record user identity, durable audit rows, or a
protocol-level confirmation exchange.

Scaffold denial, unknown action denial, and non-confirmable policy denial still
override any confirmation id.

## Persistence Gap

Plugin responses currently persist as assistant turns with provenance metadata.
That is enough to distinguish normal LLM output from plugin output in current
code, but it is not a complete audit model. A future database/API change should
store plugin results, denied actions, confirmation-required actions, and failed
plugin actions as first-class provenance records.
