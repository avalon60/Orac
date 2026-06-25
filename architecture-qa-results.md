# Orac Architectural Audit

## Executive Summary

Orac has strong intended boundaries in the guardrails: core orchestrates, plugins extend, context is mediated, DB access goes through schema surfaces, and display/web stays thin. The recent code mostly respects that direction, but several fast-moving seams have become too broad: `src/controller/orac.py` is now the main architectural pressure point, streaming/protocol contracts have drifted from the canonical schema, service plugins are modeled but not wired into the live runtime, and the voice/display path has grown into a tightly coupled state machine.

I did not find evidence that the whole repo needs a rewrite. The right path is small contract-first fixes, then extraction of the biggest control-plane responsibilities.

## Architectural Map

- Core runtime: `src/controller/orac.py` owns config, auth, DB session, LLM selection, context persistence, plugin routing, voice/TTS streaming, and protocol responses.
- LLM layer: `src/model/llm_connector.py` defines connector base plus LM Studio and Ollama adapters.
- Context/DB runtime: `src/model/context_manager.py` persists users, conversations, messages, preferences, LLM registry state through database views.
- Plugin layer: manifests under `plugins/*.json`; discovery/routing in `src/model/plugin_routing`, execution in `src/model/plugin_router.py`, service lifecycle in `src/model/plugin_service_manager.py`.
- Voice: local voice loop, STT, TTS, VAD, AEC, barge-in under `src/orac_voice`.
- Web display: browser display under `web/orac-display`, bridged by `web/orac-display/bridge.js`.
- Protocol: canonical schema under `protocol/orac_protocol/resources/json_schema/protocol.schema.json`.
- DB/APEX: object-oriented schema layout under `resources/db/schema`, APEX exports under `resources/db/apex`, with `orac_ha` explicitly plugin-bound per `resources/db/schema/AGENT_CONTEXT.md`.

## Boundary Assessment

- Clean or mostly deliberate: plugin manifest discovery is separated from code import; AEC has a crisp backend-neutral frame contract; DB guardrails are explicit; Home Assistant placeholder code appears intentional.
- Weak boundaries: core runtime directly owns too many implementation details; LLM provider behavior leaks into orchestration; stream/display protocols are partly conventional rather than schema-owned; service plugin lifecycle exists but is not part of live startup; voice client owns too much cross-component state.
- Transitional code should be labeled rather than guessed at: Home Assistant `.ini` artifacts are documented as legacy, and HA runtime placeholders explicitly say no websocket is attempted.

## Top 10 Issues By Architectural Risk

### 1. Canonical protocol and live stream frames have drifted
Severity: must fix.  
Files involved: `protocol/README.md`, `protocol/orac_protocol/resources/json_schema/protocol.schema.json`, `src/controller/orac.py`, `src/view/slave.py`, `web/orac-display/src/App.tsx`.  
Evidence: protocol docs call the schema canonical, but schema stream delta payload requires `content_delta`; runtime emits `payload.delta`, `payload.chunk`, `voice_session_id`, `turn_id`, and puts model identity in meta. Stream events are built without validation, while normal responses are validated and returned anyway on failure.  
Why it matters: external clients, voice, and web display are coupled to behavior not guaranteed by the canonical contract.  
Suggested remediation: decide whether the current wire format or schema is authoritative, then align schema, validator, server, slave, voice, and web display. Validate outbound stream frames in tests.  
Change size: small patch first, then targeted compatibility cleanup.  
Tests before changing: golden protocol tests for `stream_start`, `text_delta`, `text_chunk`, `stream_end`, TTS playback, and voice cancel frames across server, slave, and display.

### 2. Protocol validation can silently turn off
Severity: must fix.  
Files involved: `src/controller/orac.py`, `src/view/slave.py`.  
Evidence: if package and local schema import both fail, `validate_frame` becomes a no-op and `PROTOCOL_VERSION = "unknown"`.  
Why it matters: a protocol boundary that can fail open is not a boundary.  
Suggested remediation: fail closed in production startup; allow no-op validation only behind an explicit development flag.  
Change size: small patch.  
Tests before changing: startup tests for package validator, local fallback validator, and failure mode.

### 3. Core orchestrator has too many reasons to change
Severity: should fix.  
Files involved: `src/controller/orac.py`.  
Evidence: the controller imports and wires networking, LLM providers, DB credentials, context, plugins, TTS, voice events, protocol validation, and prompt policy. `handle_request` spans auth, protocol, DB health, conversation rollover, plugin execution, LLM streaming, TTS chunks, persistence, and response building.  
Why it matters: any new feature risks changing unrelated runtime behavior.  
Suggested remediation: extract narrowly: `LlmRuntime`, `ConversationRolloverService`, `VoiceStreamBridge`, `PluginExecutionService`, and keep `Orac` as the coordinator.  
Change size: larger refactor, staged.  
Tests before changing: request lifecycle contract tests for auth failure, invalid frame, normal prompt, streaming prompt, plugin-handled turn, and conversation rollover.

### 4. LLM provider-specific behavior leaks into core
Severity: should fix.  
Files involved: `src/controller/orac.py`, `src/model/llm_connector.py`.  
Evidence: provider maps are duplicated in core; core shells out to `ollama pull`; core knows LM Studio `/v1/models`; core contains Ollama `:latest` alias logic.  
Why it matters: adding OpenAI or another backend requires edits in orchestration, not just provider code.  
Suggested remediation: introduce a provider registry/factory with provider-owned availability, model aliasing, metadata discovery, and pull/load behavior.  
Change size: larger refactor after contract tests.  
Tests before changing: provider factory tests, provider availability tests, alias resolution tests, and no-shell tests for non-Ollama providers.

### 5. Streaming abstraction does not mean the same thing for every provider
Severity: should fix.  
Files involved: `src/model/llm_connector.py`, `src/controller/orac.py`.  
Evidence: base `stream_prompt_deltas` falls back to one final non-streaming delta; LM Studio does not override it; Ollama streams natively. Core treats all providers as streaming-compatible and feeds deltas into TTS chunking.  
Why it matters: voice latency, barge-in, cancellation, and UI streaming differ by provider while presenting one contract.  
Suggested remediation: make connector capabilities explicit: `supports_native_streaming`, cancellation semantics, usage metadata support, and fallback mode.  
Change size: small patch for capability flags, larger cleanup later.  
Tests before changing: provider streaming contract tests for native stream, fallback stream, usage metadata, error, and cancellation behavior.

### 6. Service and hybrid plugin lifecycle is modeled but not wired into live runtime
Severity: should fix.  
Files involved: `src/model/plugin_service_manager.py`, `src/controller/orac.py`, `plugins/home_assistant.json`.  
Evidence: `PluginServiceManager` owns lifecycle and `start_auto_services`, but `rg` shows it is only used in tests. `Orac` initialises `PluginManager` and `PluginRouter`, not the service manager. HA declares `hybrid`, `long_running`, `start_policy: auto`.  
Why it matters: manifests can declare services that never run, so the manifest model overstates runtime behavior.  
Suggested remediation: wire service manager into plugin refresh/startup/shutdown, or explicitly disable service manifests until wired.  
Change size: small patch if lifecycle is simply registered; larger if supervision is integrated with process shutdown.  
Tests before changing: Orac startup registers service/hybrid manifests, starts auto services, stops them on shutdown, and disables services with missing dependencies.

### 7. Plugin execution bypasses mature policy and provenance boundaries
Severity: should fix.  
Files involved: `src/model/plugin_router.py`, `src/model/plugin_runtime.py`, `src/controller/orac.py`, `plugins/README.md`.  
Evidence: router loads plugin code and directly calls `execute(prompt, meta)` with no timeout, input schema, confirmation policy, or execution sandbox. Plugin result is persisted as an assistant turn with a TODO to introduce explicit provenance. Plugin README says privilege models, security boundaries, and full runtime are intentionally deferred.  
Why it matters: safe weather-style plugins are fine, but device-control and external-service plugins need a stronger execution boundary.  
Suggested remediation: add a plugin execution policy layer before adding real HA control: timeouts, declared action type, confirmation requirement, entitlement checks, and separate persisted plugin-result provenance.  
Change size: larger refactor, but can be introduced incrementally.  
Tests before changing: undeclared entitlement denial, unsupported entitlement denial, timeout, plugin exception behavior, risky action confirmation, and plugin-result persistence as non-assistant provenance.

### 8. Home Assistant advertises active capabilities that are still placeholders
Severity: should fix before enabling as a real capability; leave alone if explicitly marked as roadmap-only.  
Files involved: `plugins/home_assistant.json`, `plugins/home_assistant/plugin.py`, `src/model/plugin_routing/manager.py`, `resources/db/schema/AGENT_CONTEXT.md`, `resources/db/schema/ha_ddl.sql`, `plugins/home_assistant/db/schema`.
Evidence: manifest is `enabled: true` and lists device control, state query, event listener, DB requirement, and unsupported entitlements. Implementation `can_handle` returns false and service loop explicitly says no websocket is attempted. DB schema has both monolithic DDL and object-by-object files for the same HA objects. Dependency check only verifies local schema folder existence, not installed DB version.  
Why it matters: users and future code may treat HA as production-ready when it is a scaffold.  
Suggested remediation: either disable HA until real runtime exists, or mark it as scaffold/experimental in routing eligibility and service startup. Remove or quarantine duplicate DDL sources once canonical HA DB source is chosen.  
Change size: small patch for disable/experimental flag; larger refactor for real HA.  
Tests before changing: HA is not routable/control-capable until policy, DB version check, credentials, and service health are real.

### 9. Voice local loop is an oversized integration state machine
Severity: should fix before adding more voice behavior.  
Files involved: `src/orac_voice/voice_loop_local.py`, `src/orac_voice/aec.py`.  
Evidence: the loop imports activation, capture, barge-in, STT, TTS worker, wake engines, display pipe, and slave protocol. `_send_orac_prompt` tracks many streaming/playback/barge-in booleans and directly interprets protocol frame types. AEC itself is clean and should be left as a stable low-level contract.  
Why it matters: barge-in, playback, protocol changes, and display changes can regress each other.  
Suggested remediation: extract a voice turn controller/state machine, a protocol client adapter, and a display adapter. Keep AEC frame contract unchanged.  
Change size: larger refactor.  
Tests before changing: high-level voice turn sequence tests for stream-only, stream+TTS, timeout, barge-in cancel, stale frames, and display events.

### 10. Tests are broad but overfit private implementation details
Severity: should fix.  
Files involved: `tests/test_orac_voice.py`, `tests/test_orac_context_history.py`, `tests/test_plugin_service_manager.py`.  
Evidence: tests directly instantiate `Orac.__new__`, set many private fields, import private voice functions, and assert internal frame names. They are valuable but lock in current shape.  
Why it matters: refactoring toward cleaner boundaries will be harder than it needs to be, and tests may protect incidental behavior over contracts.  
Suggested remediation: keep existing coverage, but add contract tests at the boundaries: protocol, provider streaming, plugin lifecycle, plugin policy, voice turn state machine, display event schema.  
Change size: small additions first, then refactor support.  
Tests before changing: the contract tests themselves.

## Quick Wins

- Remove the duplicate session derivation in `src/controller/orac.py`.
- Fix `raise NotImplemented(message)` to `NotImplementedError` in `src/model/llm_connector.py`.
- Replace connector `print` calls with logger calls in `src/model/llm_connector.py`.
- Add timeout to LM Studio `list_models` in `src/model/llm_connector.py`.
- Mark unused/deferred config sections such as `[openai_gateway]`, `[vector_db]`, and `compress_old_sessions` as active/deprecated/roadmap. Evidence: `resources/config/orac.ini`, `src/model/vector_manager.py`.
- Validate `ORAC_DB_OBJECT_SCHEMA` against an allowlist before interpolating object names in `src/model/context_manager.py`.

## High-Risk Areas To Avoid Changing Casually

- Protocol frame names and payloads: they affect server, slave, voice, web, tests, and future clients.
- `handle_request` conversation/session rollover logic.
- Voice playback, barge-in, and stream completion timing.
- AEC frame size/sample-rate contract. This looks deliberate and clean.
- Plugin manifest schema and routing cache hashes.
- `orac_ha` database assets, because guardrails mark them as plugin-bound.
- Credential paths and HMAC secret handling across `bin/orac.sh`, `src/view/slave.py`, `src/controller/orac.py`, `src/lib/api_key_store.py`, and `src/lib/user_security.py`.

## Recommended Refactoring Sequence

1. Add boundary contract tests first: protocol frames, provider streaming, plugin lifecycle, display events, voice turn sequences.
2. Patch fail-open protocol validation, duplicate session derivation, connector prints/timeouts, and `NotImplemented`.
3. Align protocol schema with actual stream/display payloads or migrate runtime to the schema.
4. Introduce an LLM provider registry/factory and move provider availability/probe logic out of `Orac`.
5. Wire or explicitly disable service plugin lifecycle for hybrid/service manifests.
6. Add plugin execution policy and provenance before any real Home Assistant device control.
7. Extract `VoiceStreamBridge` and voice turn handling from `src/controller/orac.py` and `src/orac_voice/voice_loop_local.py`.
8. Clean up deprecated config keys and duplicate/transitional DB/plugin artifacts only after ownership is documented.

## Suggested Guardrails For Future Codex Work

- Do not add new provider-specific behavior to `src/controller/orac.py`.
- Any new stream/display event must start with schema/test updates.
- Any plugin with external access, filesystem access, DB writes, or device control must have manifest entitlements, runtime policy, denial tests, and provenance.
- No service plugin should start its own unmanaged loop; it must run under Orac supervision.
- New config keys need a reader, a test, and documented ownership.
- No broad `except Exception` at architectural boundaries without a typed reason, log policy, and test.
- DB changes stay object-by-object and preserve schema direction; `orac_ha` stays plugin-bound.
