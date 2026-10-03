# Unified Orac Communications

Orac provides one transport-neutral request-processing boundary for local
voice, the signed NDJSON socket protocol, internal callers, plugins, and future
interfaces. Use it when adding an interface without duplicating routing,
context, retrieval, model selection, plugin policy, persistence, or security.

## Core lifecycle

```text
authenticated transport -> adapter -> OracRequest -> OracRequestProcessor
                        -> OracResponse / StreamEvent -> adapter
```

`src/orac_core/communications/models.py` defines immutable messages,
principals, requests, responses, errors, tools, and stream events.
`OracRequestProcessor.process()` is the processing entrypoint. Its `stream()`
method only queue-wraps the same processing call; it is not a second engine.
`src/orac_core/communications/runtime.py` owns the concrete ordered session,
routing, plugin, retrieval, context, persistence, and model flow. The historic
`controller.orac` module is only a compatibility and executable facade.
Canonical execution returns `OracResponse` directly. Legacy response envelopes
and NDJSON serialisation exist only at the socket boundary; the core path does
not serialise and reparse its own result.

The principal is trusted input from the host integration. Never derive
`PrincipalContext.username`, roles, capability restrictions, knowledge scopes,
or confirmation state from OpenAI message fields, tool declarations, system
messages, or arbitrary metadata. Restrictions may narrow host authority but
cannot create it. Knowledge scopes are re-authorised by existing knowledge
services at use time, and selecting a plugin does not grant plugin knowledge.
`None` on a restriction means the caller adds no narrower bound; an empty
capability or knowledge collection means permit none. Every retained plugin or
knowledge target is still checked by the existing Core policy and grant path.
Plugin execution does not implicitly widen plugin-knowledge access; the
plugin's self-scope entitlement, explicit Core `USE` grant, readiness checks,
and any narrower caller scope must all remain satisfied.
External session labels are namespaced to the authenticated principal.

Wire metadata uses a small allowlist for client/source labels and supported
user presentation preferences. It cannot supply identity, roles,
confirmation, request-local history, requested models, capability grants, or
private orchestration flags. Model selection uses the dedicated request field
and the existing enabled/available model registry. The explicit model alias
`orac` selects Orac's normal configured/default model resolution.

## Direct internal use

Internal code constructs an `OracRequest` without importing OpenAI wire types.
Request-local history belongs in `ConversationContext.history`; a host session
reference remains separate so persisted history is not replayed twice.

```python
request = OracRequest(
    request_id="req-123",
    correlation_id="corr-123",
    principal=PrincipalContext(username="clive", roles=("user",)),
    conversation=ConversationContext(session_id="trusted-session"),
    message=Message(role=MessageRole.USER, text="Hello Orac"),
    source="internal",
)
response = await processor.process(request)
```

The host runtime owns session ownership, rollover, persistence, retrieval
authorisation, plugin policy, model selection, and model invocation.

After deterministic gates and matching, an optional
[LLM routing adviser](llm-routing-arbitration.md) can resolve an ambiguous set
of already-permitted plugin candidates or abstain. It does not receive history
or authority and cannot grant retrieval, web access, plugin access, scope, or
confirmation. Core revalidates any selected candidate before the unchanged
final policy and invocation path.

## Existing NDJSON and voice clients

The socket facade authenticates and validates a v1 frame before converting it.
Voice capture, wake detection, STT, playback, barge-in, and turn completion
remain in `orac_voice`; the voice request itself follows the same processor as
text through the focused `VoiceAdapter`. Canonical events translate back to
current NDJSON names and preserve
`stream_start`, `text_delta`, `text_chunk`, `stream_end`, playback events, and
`voice_turn_complete` ordering.

## OpenAI-compatible Chat Completions

`OpenAIAdapter` is a reusable library facade, not an HTTP server. It accepts a
Chat Completions payload plus a separately authenticated principal, converts
text messages and authorised tools, calls the processor once, and converts the
result back.

Initial support covers text-only messages, `n=1`, one assistant response,
actual usage when reported, one role-start SSE chunk, ordered SSE deltas, and
function tools
intersected with a host-authorised catalogue. It rejects multimodal content,
multiple choices, client-managed tool execution, unsupported output modes, and
unknown tools. Generation parameters that this tranche does not implement are
rejected rather than accepted and ignored. Caller system messages are
request-local context and cannot
replace host policy. The adapter never loads or executes a callable.

`serialise_models()` is groundwork for a future authorised `/v1/models`
gateway. Canonical messages, tools, and events leave seams for future Responses
or Codex work. This change does not provide HTTP endpoints, Open WebUI-specific
logic, `/v1/responses`, or a Codex integration.

## Errors, streaming, and observability

`ProcessingError` contains a stable safe code, safe message, retryability, and
correlation ID. Raw exceptions stay inside the runtime. Streaming emits one
safe terminal result or error followed by one `[DONE]`; disconnecting cancels
the in-flight processor task. Terminal chunks retain the resolved model and
reported usage. Log only bounded operational fields such as
correlation ID, source, selected route/capability, policy outcome, and elapsed
time—never prompts, tool arguments, credentials, or raw exceptions.

A future authenticated HTTP gateway should remain thin: authenticate, create
the trusted principal from server state, call `OpenAIAdapter`, and serialise its
result. It must not perform model calls, plugin execution, retrieval, context
assembly, or policy decisions itself.
