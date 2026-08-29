# Unified Model-Aware Context Budgeting

Phase 2B gives primary dialogue invocations one host-owned context allocation
and final safety decision. It does not change conversation retention,
retrieval authority, conversational-memory checkpoints, PROJECT scope, or
PLUGIN scope.

The shipped configuration enables the planner in shadow mode. Shadow mode
calculates and records the decision while preserving the existing prompt. Move
to enforcement only after reviewing provider/runtime telemetry for the models
actually in service.

## Capacity Model

The enabled `llm_registry` row is the governed ceiling for the exact selected
provider and model. A reliable provider observation may report a smaller active
runtime allocation. Orac uses:

```text
effective_context_limit = min(
    governed_model_context_limit,
    known_runtime_execution_context_limit,
)
```

When the runtime limit is unavailable, Orac uses the governed registry ceiling
and records `CTX_RUNTIME_LIMIT_UNKNOWN`; it does not guess from a model name or
provider default. A smaller positive runtime allocation is valid and produces
the diagnostic `CTX_RUNTIME_LIMIT_REDUCED`. It is not a provider
incompatibility. The runtime can never raise the governed ceiling.

The immutable model snapshot also records the registry row version and safe
runtime observation metadata. When a reliable runtime observation or governed
registry row changes before invocation, Orac replans once against the new
snapshot and fails safely if it cannot obtain a current, fitting plan.

## Estimation and Reserve

Provider connectors construct the exact context-bearing representation used by
their invocation contract, including normalized chat messages, system wrappers,
tool schemas, and tool messages where applicable. Orac then runs the
authoritative conservative estimator over that serialization. This is an exact
provider representation with a conservative token estimate; it is not an exact
token count unless the selected model's exact tokenizer is used.

Estimator uncertainty and deliberate unused context are independent:

- `estimator_uncertainty_margin_percent` protects against estimator error. It
  is applied exactly once to the base preflight estimate.
- `context_safety_percent` and `context_safety_min_tokens` retain deliberate
  unused headroom after estimation.

Every enforced provider-bound invocation must satisfy:

```text
base_preflight_estimated_tokens
+ estimator_uncertainty_tokens
+ response_allowance
+ context_safety_reserve
<= effective_context_limit
```

Provider-reported prompt tokens are post-invocation calibration evidence only.
They are recorded separately from the preflight estimate and never
retroactively approve a rejected invocation or automatically change policy.

## Allocation

Mandatory instructions and the current request are always selected first. If
they cannot fit with the response allowance and both safety controls, Orac
rejects the invocation with `CTX_MANDATORY_OVERFLOW`.

Optional context is selected deterministically in this order:

1. the configured minimum of newest completed dialogue exchanges;
2. bounded primary web or local knowledge evidence;
3. bounded conversational-memory evidence;
4. additional recent completed dialogue exchanges.

Conversation history is exchange-atomic: a user/assistant exchange is selected
or omitted as a whole. Omission changes only the live prompt projection; the
authoritative persisted conversation record is not deleted. Evidence packs
remain bounded by their existing domain policies and authorization services
before entering the shared planner.

The resulting prepared invocation is immutable. The final safety guard uses
the provider-bound serialization, not component estimates added independently.
This prevents wrapper or tool-framing overhead from escaping accounting.

## Governed Retrieval and Output Retry

Phase 2A remains independently authorized. When a governed retrieval tool is
advertised, Phase 2B includes the exact provider tool schema framing in the
initial estimate. After retrieval, the tools-disabled continuation is checked
again with the ephemeral assistant tool-call and bounded tool-result messages.
Those messages remain ephemeral and are not persisted as conversation turns.

If a non-streaming response exhausts its output allowance, enforcement mode
does not let the connector grow output independently. Orac increases the
allowance under the existing retry policy, replans the whole prompt, and may
omit lower-priority optional context before retrying. An unsafe retry is not
invoked.

## Audit, Telemetry, and Rollout

Assistant turn metadata records content-free context-budget data, including:

- governed, observed runtime, and effective context limits;
- whether runtime capacity constrained the registry maximum;
- base estimate, applied uncertainty, response allowance, and context reserve;
- selected and omitted component counts and safe reason codes;
- serializer and estimator versions;
- provider-reported prompt tokens and estimate-to-actual deltas when available.

Prompt text, evidence text, and provider serialization are not copied into this
telemetry. Serialization fingerprints support correlation without recording
content.

Recommended rollout:

1. Leave `enabled = true` and `shadow_mode = true`.
2. Collect representative Ollama and LM Studio usage, including ordinary,
   evidence-backed, governed-tool, and output-retry turns.
3. Confirm no mandatory overflows, unsafe undercount pattern, or stale runtime
   observations for supported provider/runtime/model combinations.
4. Review any proposed reduction from the initial 20 percent estimator margin.
   The validated configuration floor is 10 percent; changes are explicit
   operator/product decisions and are never telemetry-driven mutations.
5. Set `shadow_mode = false` and restart Orac to enforce decisions.

No database migration is required for Phase 2B.
