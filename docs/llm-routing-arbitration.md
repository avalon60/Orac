# LLM-Assisted Routing Arbitration

Orac can optionally ask a model for one bounded routing judgement when plugin
gates have already run and deterministic routing is unresolved or ambiguous.
This is useful when several permitted capabilities are plausible, but it is
deliberately conservative: a missed plugin interception is safer than sending
an ordinary informational question to a plugin.

```text
request
  |
  v
deterministic authentication / policy / scope gates
  |
  v
permitted plugin candidates
  |
  v
deterministic matching
  |
  +--> confident interceptor / explicit route --> normal route
  |
  v
LLM routing adviser
  |
  +--> strong fit --> selected permitted candidate
  |
  +--> weak / uncertain --> abstain
  |
  v
deterministic identity and eligibility revalidation
  |
  v
final policy / confirmation / invocation
```

The adviser is not an authentication, authorisation, policy, safety, scope, or
confirmation mechanism. It receives only candidates already admitted by Core's
side-effect-free eligibility checks. It cannot name an arbitrary capability:
the response schema contains the exact permitted identifiers, and Core resolves
an accepted identifier back to the original candidate before repeating
eligibility checks. The existing final route policy still creates or consumes
confirmation and invokes the plugin.

## Conservative decisions and fallback

The model must not choose the closest candidate. It is instructed to select a
plugin only when the current request clearly requires or strongly benefits from
that capability. Shared nouns, broad topics, generic verbs such as `check`,
`find`, `show`, or `tell`, loose embedding similarity, and topical adjacency do
not justify interception. Uncertainty and explicit abstention are valid.

The strict output contains `selected_route`, `selected_candidate_id`,
`confidence`, and a short diagnostic `reason`. The only initial route values
are `plugin`, `direct_llm`, and `no_plugin_match`. Both non-plugin values return
to the established conversational path. Earlier authorised knowledge and web
routes retain their current precedence; this tranche does not invent a late
retrieval or web-search execution contract. Consequently, raw request metadata
or model output cannot advertise or grant those routes.

A plugin decision below `min_confidence`, an informational false-positive
pattern, malformed JSON, extra fields, an unknown route or identifier,
non-finite confidence, timeout, connection failure, provider error, or failed
revalidation falls back without invoking a plugin. Semantic correctness cannot
be guaranteed mathematically, but the bounded candidate set, conservative
rejection rules, and Core revalidation provide hard authority boundaries.

## Configuration examples

Disabled arbitration is explicit and does not initialise a provider:

```ini
[arbitrator]
enabled = false
```

Ollama is the recommended initial and integration-test provider:

```ini
[arbitrator]
enabled = true
provider = ollama
model = qwen3.6-48K:latest
endpoint = http://localhost:11434
timeout_seconds = 10
min_confidence = 0.90
api_key_env =
```

The primary conversation model and arbitration model are logically independent.
They may initially use the same Ollama endpoint and model without loading a
second model. Later, change only the `[arbitrator]` values to substitute a small
router.

An OpenAI-compatible endpoint can be local or remote; the name describes the
HTTP protocol and does not imply OpenAI cloud:

```ini
[arbitrator]
enabled = true
provider = openai_compatible
model = router-model
endpoint = http://localhost:9000/v1
timeout_seconds = 10
min_confidence = 0.90
api_key_env = LOCAL_ROUTER_API_KEY
```

When `api_key_env` is set, its value is the name of an environment variable.
The secret itself remains outside the INI file and arbitration prompt.

`edge_runtime` is a registration point for a concrete CPU, NPU, embedded, or
vendor accelerator adapter. It can avoid consuming main-GPU VRAM. There is no
universal edge API, so the shipped Core does not fabricate one:

```ini
[arbitrator]
enabled = true
provider = edge_runtime
model = router-model
endpoint = runtime-specific-value
timeout_seconds = 10
min_confidence = 0.90
api_key_env =
```

The endpoint is optional and runtime specific for an injected edge factory.
Without a registered concrete factory, startup records `runtime_unavailable`
and deterministic routing continues.

## Properties

- `enabled` is optional and defaults to `false`. It is the only disable
  mechanism. When false, other arbitration properties are not validated or
  used.
- `provider` is required when enabled. Valid values are `ollama`,
  `openai_compatible`, and `edge_runtime`. Unknown values are configuration
  errors.
- `model` is required and non-empty when enabled. An empty value is a
  configuration error, not a disable signal.
- `endpoint` is a required non-empty HTTP(S) URL for `ollama` and
  `openai_compatible`. It is optional and runtime specific for `edge_runtime`.
- `timeout_seconds` is optional, defaults to `10`, and accepts `0.1` through
  `120` seconds.
- `min_confidence` is optional, defaults to `0.90`, and accepts a finite value
  from `0` through `1`. It is a false-positive rejection threshold, never an
  authorisation signal.
- `api_key_env` is optional. For `openai_compatible`, it names an environment
  variable containing the protocol credential. It never contains the secret.

Environment overrides follow the normal Orac convention, for example
`ORAC__ARBITRATOR__MODEL=small-router`. If enabled configuration is missing or
invalid, arbitration is unavailable and Orac logs a sanitised reason while
continuing deterministic routing. Empty model or HTTP endpoint values do not
disable arbitration.

## Provider extension contract

A provider implements `ArbitrationProvider.complete(messages=...,
response_schema=...)` and returns a string or mapping for strict validation.
Messages contain only the current bounded request and concise semantics for the
already-permitted candidates. They contain no conversation history,
credentials, extracted plugin arguments, policy internals, or inaccessible
knowledge metadata.

Register a future edge adapter by supplying an `EdgeRuntimeFactory` to
`create_arbitration_provider`. The adapter owns runtime-specific request
construction, timeout handling, and conversion of runtime failures to
`ArbitrationProviderError` categories. It must honour the supplied response
schema and must not perform routing, policy, confirmation, or invocation.
For a concrete deployment, the runtime composition point supplies a factory,
then injects the returned provider into `LLMRoutingAdviser` through
`PluginArbiter`; the decision logic remains unchanged. For example:

```python
configuration = ArbitrationConfiguration.from_config(config_mgr)
provider = create_arbitration_provider(
    configuration,
    edge_runtime_factory=lambda settings: MyEdgeRouter(settings),
)
adviser = LLMRoutingAdviser(
    provider=provider,
    provider_name=configuration.provider,
    model=configuration.model,
    min_confidence=configuration.min_confidence,
)
arbiter = PluginArbiter(routing_adviser=adviser)
```

The stock Orac runtime does not register a concrete edge factory. A deployment
must register one at its composition boundary; merely selecting
`provider = edge_runtime` records `runtime_unavailable` and falls back safely.
Provider tests should cover strict structured output, timeout and connection
failures, malformed envelopes, credential handling, and an injected fake. The
decision and revalidation code does not change when a provider is added.

For an opt-in Ollama smoke test, use the currently configured primary model and
endpoint as independent environment inputs:

```bash
ORAC_ARBITRATION_SMOKE_MODEL=qwen3.6-48K:latest \
ORAC_ARBITRATION_SMOKE_ENDPOINT=http://localhost:11434 \
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/test_arbitration_ollama_smoke.py
```

The test uses synthetic operational and informational candidates; it does not
invoke a real plugin or pull another model. It skips unless both variables are
set. A future
deployment can instead use a GPU-hosted large primary model and a 7B router on
an edge/NPU runtime by changing configuration and registering that adapter.
