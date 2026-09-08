# Configuration Parameters

This is the canonical reference for `resources/config/orac.ini`. It documents every shipped section and key. Plugin-local `plugin.ini` files are documented with their plugins and are not part of this reference.

## Reading This Reference

- **Shipped value** is the value in the repository's `orac.ini`.
- **Runtime fallback** is used only when a loader supplies a default and the key is absent.
- **Status** distinguishes active, optional, experimental, and reserved settings.
- Empty optional values do not imply that secrets should be stored in the INI file.

For installation context, see [Installation](installation.md). For subsystem behavior, see [Internet Retrieval](retrieval.md), [Voice Pipeline](voice-pipeline.md), and [Plugins](plugins.md).
Runtime user preference precedence, validation, and post-resolution behaviour
are documented in [Runtime User Preferences](user_preferences.md).

## `[global]`

Project-wide identity settings.

### `project_identifier`

- **Type:** string
- **Shipped value:** `Orac`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Identifies the project in connection-management and deployment tooling.

**Example:** `project_identifier = Orac`

## `[service]`

Local or remote LLM provider and generation-budget settings.

### `llm_service_id`

- **Type:** string
- **Shipped value:** `ollama`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** Yes for the configured LLM path
- **Allowed values:** Configured provider identifier, such as `ollama` or `lmstudio`
- **Status:** active

Selects the configured LLM provider implementation.

**Example:** `llm_service_id = ollama`

### `default_model_name`

- **Type:** string
- **Shipped value:** `qwen3.6-48K:latest`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** Yes for the configured LLM path
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Names the model requested from the configured LLM service.

**Example:** `default_model_name = qwen3.6-48K:latest`

### `service_url`

- **Type:** string
- **Shipped value:** `http://localhost:11434`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** Yes for the configured LLM path
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Base URL for the configured LLM service.

**Example:** `service_url = http://localhost:11434`

### `default_num_predict`

- **Type:** integer
- **Shipped value:** `2048`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Initial output-token budget for model generation.

**Example:** `default_num_predict = 2048`

### `num_predict_incr_pct`

- **Type:** integer
- **Shipped value:** `100`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Percentage increase applied when generation reaches the token limit.

**Example:** `num_predict_incr_pct = 100`

## `[database]`

Named encrypted database connections used by core and plugin runtime paths.

`dsn_credential_entry` and `plugin_dsn_credential_entry` are lookup keys for
entries in the encrypted DSN credentials store. They are not `tnsnames.ora`
aliases. The selected credential entry's `resource_id` contains the Oracle DSN,
which may itself be a TNS alias.

This is a breaking configuration rename. Existing configurations must replace
`connection_name` and `plugin_connection_name`; the old keys are no longer
read. Environment overrides must likewise use
`ORAC__DATABASE__DSN_CREDENTIAL_ENTRY` and
`ORAC__DATABASE__PLUGIN_DSN_CREDENTIAL_ENTRY`.

### `dsn_credential_entry`

- **Type:** string
- **Shipped value:** `orac-service`
- **Runtime fallback:** None; the configured key is required
- **Required:** Yes for the corresponding database path
- **Allowed values:** A named entry in the encrypted DSN credentials store
- **Status:** active

Selects the encrypted least-privilege core runtime credential entry.

**Example:** `dsn_credential_entry = orac-service`

### `plugin_dsn_credential_entry`

- **Type:** string
- **Shipped value:** `orac-plugin`
- **Runtime fallback:** None when configuration is supplied; standalone factories without a configuration manager use `orac-plugin`
- **Required:** Yes for the corresponding database path
- **Allowed values:** A named entry in the encrypted DSN credentials store
- **Status:** active

Selects the encrypted plugin-bridge runtime credential entry.

**Example:** `plugin_dsn_credential_entry = orac-plugin`

## `[client]`

Protocol client timeout and console presentation settings.

### `llm_timeout`

- **Type:** integer
- **Shipped value:** `120`
- **Runtime fallback:** `60` in the LLM connector; the legacy client view uses `90`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Maximum time to wait for an LLM or protocol client operation.

**Example:** `llm_timeout = 120`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `show_timestamp`

- **Type:** boolean
- **Shipped value:** `false`
- **Runtime fallback:** `true`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures show timestamp for the `[client]` subsystem.

**Example:** `show_timestamp = false`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

## `[settings]`

General response-processing behavior.

### `strip_reasoning_tags_default`

- **Type:** boolean
- **Shipped value:** `false`
- **Runtime fallback:** `true`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Removes model reasoning-tag content from user-facing output when enabled.

**Example:** `strip_reasoning_tags_default = false`

**Notes:** This is a runtime preference default. Saved user preferences and explicit request metadata take precedence.

### `timezone_default`

- **Type:** string
- **Shipped value:** `Europe/London`
- **Runtime fallback:** `Europe/London`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** IANA timezone names
- **Status:** active

Default timezone used when no request metadata or saved user preference is set.

**Example:** `timezone_default = Europe/London`

### `date_format_default`

- **Type:** string
- **Shipped value:** `DD-MON-YYYY HH24:MI`
- **Runtime fallback:** `DD-MON-YYYY HH24:MI`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Values from the `DATE_FORMAT` preference LOV
- **Status:** active

Default user-facing date/time format used when no saved preference is set.

**Example:** `date_format_default = DD-MON-YYYY HH24:MI`

### `force_concise_default`

- **Type:** boolean
- **Shipped value:** `false`
- **Runtime fallback:** `false`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Default concise-response preference used when no saved preference is set.

**Example:** `force_concise_default = false`

### `max_tokens_default`

- **Type:** integer
- **Shipped value:** `2048`
- **Runtime fallback:** no explicit runtime override
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Positive integers
- **Status:** active

Default maximum response-token budget used when no saved preference is set.

**Example:** `max_tokens_default = 2048`

### `show_reasoning_default`

- **Type:** boolean
- **Shipped value:** `false`
- **Runtime fallback:** `false`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Default permission flag for provider-visible reasoning summaries where supported.

**Example:** `show_reasoning_default = false`

### `tts_rate_default`

- **Type:** number
- **Shipped value:** `0.95`
- **Runtime fallback:** provider default
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `0.25` to `4.0`
- **Status:** active

Default text-to-speech rate used when the provider supports per-request rate.

**Example:** `tts_rate_default = 0.95`

**Notes:** This is a runtime preference default. It is an engine-neutral hint;
Kokoro maps it to `speed`, while Piper currently ignores it safely.

### `tts_pitch_default`

- **Type:** number
- **Shipped value:** `0.0`
- **Runtime fallback:** provider default
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `-10.0` to `10.0`
- **Status:** active

Default text-to-speech pitch used when the provider supports per-request pitch.

**Example:** `tts_pitch_default = 0.0`

**Notes:** This is a runtime preference default. It is an engine-neutral hint;
Kokoro and Piper currently ignore pitch safely.

## `[context]`

Conversation history, prompt policy, and rollover behavior.

### `enable_context_history`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Enables persisted conversation history during context assembly.

**Example:** `enable_context_history = true`

Persisted conversation retention and live prompt history are separate. Orac no
longer deletes old messages as part of normal prompt trimming. Explicit
conversation deletion remains a separate lifecycle operation.

### `enable_prompt_dump`

- **Type:** boolean
- **Shipped value:** `false`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Writes assembled prompts to debug logs; enable only for local diagnostics.
The operator command `bin/orac-ctl.sh dump-context` independently arms a
one-shot dump for the next eligible request even when this setting is `false`.
The marker is consumed once; persistent dumping does not leave it armed.

**Example:** `enable_prompt_dump = false`

### `compress_old_sessions`

- **Type:** boolean
- **Shipped value:** `yes`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Reserved switch for future old-session summarisation; currently inactive.

**Example:** `compress_old_sessions = yes`

### `history_turn_pairs`

- **Type:** integer
- **Shipped value:** `24`
- **Runtime fallback:** `6`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Maximum recent user/assistant turn pairs considered for context.

**Example:** `history_turn_pairs = 24`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `reply_language`

- **Type:** string
- **Shipped value:** `English`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures reply language for the `[context]` subsystem.

**Example:** `reply_language = English`

### `system_prompt_policy_file`

- **Type:** path/string
- **Shipped value:** `resources/config/orac_system_prompt.yaml`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures system prompt policy file for the `[context]` subsystem.

**Example:** `system_prompt_policy_file = resources/config/orac_system_prompt.yaml`

### `economy`

- **Type:** string
- **Shipped value:** `normal`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `thrifty`, `normal`, `lavish`
- **Status:** active

Configures economy for the `[context]` subsystem.

**Example:** `economy = normal`

### `history_budget_tokens`

- **Type:** string
- **Shipped value:** _empty_
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; empty disables or defers the optional value
- **Allowed values:** Any value valid for the described subsystem
- **Status:** optional

Configures history budget tokens for the `[context]` subsystem.

**Example:** `history_budget_tokens = `

### `history_budget_reserve`

- **Type:** integer
- **Shipped value:** `300`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures history budget reserve for the `[context]` subsystem.

**Example:** `history_budget_reserve = 300`

### `session_scope`

- **Type:** string
- **Shipped value:** `user`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `user`, `user+client`
- **Status:** active

Configures session scope for the `[context]` subsystem.

**Example:** `session_scope = user`

### `normalize_client`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures normalize client for the `[context]` subsystem.

**Example:** `normalize_client = true`

### `allow_external_session_id`

- **Type:** boolean
- **Shipped value:** `false`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures allow external session id for the `[context]` subsystem.

**Example:** `allow_external_session_id = false`

### `conversation_timeout`

- **Type:** integer
- **Shipped value:** `60`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Minutes of inactivity before conversation rollover; zero disables rollover.

**Example:** `conversation_timeout = 60`

### `archive_on_rollover`

- **Type:** boolean
- **Shipped value:** `false`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures archive on rollover for the `[context]` subsystem.

**Example:** `archive_on_rollover = false`

### `close_on_rollover`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures close on rollover for the `[context]` subsystem.

**Example:** `close_on_rollover = true`

## `[context_budget]`

Unified model-aware context allocation and provider-bound preflight safety. See
[Unified Model-Aware Context Budgeting](context-budgeting.md) for the capacity,
allocation, telemetry, and rollout contract.

### `enabled`

- **Type:** boolean
- **Shipped value:** `true`
- **Allowed values:** `true`, `false`
- **Status:** active

Enables Phase 2B planning. Disabling it retains the legacy prompt assembly
path.

### `shadow_mode`

- **Type:** boolean
- **Shipped value:** `true`
- **Allowed values:** `true`, `false`
- **Status:** active

When true, Orac calculates and records the unified decision but sends the
legacy prompt. Set false only after reviewing representative shadow telemetry.

### `estimator_uncertainty_margin_percent`

- **Type:** integer
- **Shipped value:** `20`
- **Allowed values:** `10` to `50`
- **Status:** active

Uncertainty uplift applied exactly once to the conservative estimate over the
provider-bound context serialization. It is distinct from deliberate context
headroom and is changed only through reviewed configuration.

### `context_safety_percent`

- **Type:** integer
- **Shipped value:** `5`
- **Allowed values:** `5` to `25`
- **Status:** active

Percentage of the effective context limit deliberately left unused after
estimation.

### `context_safety_min_tokens`

- **Type:** integer
- **Shipped value:** `256`
- **Allowed values:** `256` to `8192`
- **Status:** active

Minimum deliberate unused context headroom. Orac uses the greater of this
value and `context_safety_percent` of the effective limit.

### `recent_dialogue_min_exchanges`

- **Type:** integer
- **Shipped value:** `1`
- **Allowed values:** `1` to `4`
- **Status:** active

Newest completed user/assistant exchanges considered before evidence and older
history. Selection is exchange-atomic and never deletes persisted messages.

## `[conversation_memory]`

Provenance-backed recall over retained conversation history. The direct Phase 1
path uses a deterministic explicit intent policy and a host-owned retrieval
service. The separate governed-retrieval feature may expose that same service
through a bounded model-callable CONVERSATION domain without changing its
authority contract. No MCP surface is exposed. See
[Conversation Context, Memory, and RAG](conversation-context-memory-and-rag.md).

### `enabled`

- **Type:** boolean
- **Shipped value:** `true`

Enables checkpoint materialisation, conservative explicit recall, and
conversation-domain availability to otherwise eligible governed retrieval.
Persisted conversation retention and non-destructive live-history projection
do not depend on this switch.

### `checkpoint_exchange_count`

- **Type:** positive integer
- **Shipped value:** `20`

Number of completed user/assistant exchanges in each canonical checkpoint.

### `materialisation_profile`

- **Type:** string
- **Shipped value:** `conversation-memory-v2`

Idempotency and compatibility identity for checkpoint materialisation.

### `prompt_version`

- **Type:** string
- **Shipped value:** `conversation-v1`

Version recorded with each derived summary.

### `embedding_model_id`

- **Type:** string
- **Shipped value:** `nomic-embed-text:latest`

Pinned Phase 1 embedding profile for summaries and source messages.

### `embedding_provider`

- **Type:** string
- **Shipped value:** `ollama`
- **Allowed values:** `ollama`

Provider used only for conversational-memory summary and source-message
embeddings. Deterministic fixtures must inject a test provider directly and
cannot be selected through production configuration.

### `embedding_service_url`

- **Type:** HTTP(S) URL
- **Shipped value:** `http://localhost:11434`

Trusted host configuration for the Ollama embedding endpoint. Dialogue or
model output cannot override this URL.

### `embedding_dimensions`

- **Type:** positive integer
- **Shipped value:** `768`

Required dimensions for the pinned embedding profile.

### `summary_max_chars`

- **Type:** positive integer
- **Shipped value:** `6000`

Maximum size of the deterministic derived summary.

### `batch_size`

- **Type:** positive integer
- **Shipped value:** `4`

Maximum materialisation requests processed during one scheduled worker tick.

### `max_attempts`

- **Type:** positive integer
- **Shipped value:** `5`

Retry limit before a materialisation request becomes terminally failed.

### `max_checkpoint_candidates`

- **Type:** positive integer
- **Shipped value:** `40`

Maximum principal-owned checkpoints considered during summary discovery.

### `max_selected_checkpoints`

- **Type:** positive integer
- **Shipped value:** `4`

Maximum discovered checkpoints passed to source-message retrieval.

### `max_source_candidates`

- **Type:** positive integer
- **Shipped value:** `80`

Maximum lineage-backed source messages considered during evidence selection.

### `min_summary_score`

- **Type:** number
- **Shipped value:** `0.05`

Minimum cosine similarity for summary-level discovery.

### `min_source_score`

- **Type:** number
- **Shipped value:** `0.05`

Minimum cosine similarity for source-message evidence.

### `max_evidence_tokens`

- **Type:** positive integer
- **Shipped value:** `1200`

Hard local ceiling for memory evidence before model headroom is applied.

### `context_safety_tokens`

- **Type:** positive integer
- **Shipped value:** `256`

Minimum prompt safety reserve retained when memory evidence is added.

The host derives the authenticated principal, active conversation,
recent-message exclusions, and effective evidence budget; they are not
caller-selectable retrieval fields.

## `[governed_retrieval]`

Phase 2A model-facing, read-only retrieval mediation. Enabling the feature does
not make a model eligible by itself: the selected concrete model must have
current governed structured-tool capability evidence, provider adapter support,
safe context headroom, and acceptable runtime health.

### `enabled`

- **Type:** boolean
- **Shipped value:** `true`

Enables capability/evidence-based resolution of `STREAMING`, `BUFFERED`, or
`NONE`. It never overrides missing or rejected model evidence.

### `stream_commit_delay_ms`

- **Type:** integer
- **Shipped value:** `350`
- **Allowed range:** `100` to `1000`

Maximum pre-tool delay before buffered visible assistant text is committed on
the next visible delta. This is host configuration and is never model supplied.

### `stream_commit_max_characters`

- **Type:** integer
- **Shipped value:** `128`
- **Allowed range:** `32` to `512`

Maximum visible characters retained by the pre-tool commit gate. Once text is
committed, retrieval authority for that turn closes.

### `max_evidence_tokens`

- **Type:** integer
- **Shipped value:** `1200`
- **Allowed range:** `64` to `4096`

Independent ceiling for governed tool evidence. Actual evidence is reduced to
the selected model's remaining safe context headroom.

### `context_safety_tokens`

- **Type:** integer
- **Shipped value:** `256`
- **Allowed range:** `128` to `4096`

Minimum reserve retained when accounting for the base prompt, tool schema,
provider framing, response allowance, and serialized tool result.

### `project_scope`

- **Type:** canonical host scope (`PROJECT:key`) or empty
- **Shipped value:** `PROJECT:ORAC_CORE`

Host-owned PROJECT binding offered only after the existing Oracle RAG USE
authorization succeeds. The model cannot select or replace the scope key.

This is the legacy Phase 2A binding and remains active while Phase 2C is
disabled or running in shadow mode.

### Phase 2C discovery settings

The effective rollout states are:

| `domain_discovery_enabled` | `domain_discovery_shadow_mode` | Behaviour |
| --- | --- | --- |
| `false` | `false` | Phase 2C discovery is off. |
| `false` | `true` | Explicit diagnostic/development shadow state; Phase 2A remains model-facing. |
| `true` | `false` | Shipped active state; Phase 2C handle-enumerated domain offers are model-facing. |
| `true` | `true` | Invalid configuration; startup rejects the ambiguous state. |

### `domain_discovery_enabled`

- **Type:** boolean
- **Shipped value:** `true`

Enables invocation-scoped semantic domain offers instead of the legacy binding.

### `domain_discovery_shadow_mode`

- **Type:** boolean
- **Shipped value:** `false`

When explicitly enabled while discovery is off, evaluates the current
authorised catalogue while preserving Phase 2A output. This is diagnostic and
must not be combined with enabled discovery.

### `min_effective_context_tokens`

- **Type:** integer
- **Shipped value:** `32768`

Minimum effective context for model-controlled governed-tool and Phase 2C
discovery. This does not gate explicit host-mediated bounded knowledge-source
retrieval, which retains its own context checks.

This floor is not the only suppression control. Setting `enabled = false`
disables the governed tool path for every model, and setting
`domain_discovery_enabled = false` disables active Phase 2C discovery even for
a qualifying model. The shipped values are both `true`; shadow remains an
explicit diagnostic/development selection rather than an automatic rollout
state.

### `descriptor_embedding_profile`

- **Type:** logical profile name
- **Shipped value:** `domain_discovery`

Pins discovery to the independent Core embedding profile.

### `domain_descriptor_schema_version`

- **Type:** version string
- **Shipped value:** `domain-descriptor-v1`

Invalidates cache identity when descriptor construction changes.

### `domain_min_relevance_score`

- **Type:** number from `0` to `1`
- **Shipped value:** `0.50`

Minimum combined score for PROJECT or eligible PLUGIN advertisement.

### `domain_semantic_weight`

- **Type:** number from `0` to `1`
- **Shipped value:** `0.85`

Embedding-similarity share of discovery ranking.

### `domain_lexical_weight`

- **Type:** number from `0` to `1`
- **Shipped value:** `0.15`

Query-term coverage share. Both weights must sum to `1`.

### `domain_embedding_batch_size`

- **Type:** integer from `1` to `512`
- **Shipped value:** `64`

Maximum cold descriptor vectors generated in one provider request.

### `domain_catalogue_hard_limit`

- **Type:** integer from `128` to `10000`
- **Shipped value:** `4096`

Exceptional defensive limit, not a normal shortlist or evaluation cliff.

### `max_advertised_domains`

- **Type:** integer from `1` to `8`
- **Shipped value:** `3`

Maximum total PROJECT, CONVERSATION, and PLUGIN advertisements.

### `max_selected_domains`

- **Type:** integer from `1` to `3`
- **Shipped value:** `2`

Maximum unique advertised handles accepted in the single tool call.

### `max_catalogue_characters`

- **Type:** integer from `256` to `8000`
- **Shipped value:** `2000`

Hard character bound for the safe model-facing catalogue instruction.

### `max_federated_evidence_items`

- **Type:** integer from `1` to `20`
- **Shipped value:** `6`

Maximum merged evidence candidates before Phase 2B final accounting.

## `[embedding.domain_discovery]`

The independent Core semantic profile used only for domain-descriptor ranking.

### `provider`

- **Type:** provider code
- **Shipped value:** `ollama`

Phase 2C v1 accepts the existing Ollama provider implementation.

### `service_url`

- **Type:** HTTP(S) URL
- **Shipped value:** `http://localhost:11434`

Trusted host endpoint for descriptor and per-turn query embeddings.

### `model_id`

- **Type:** string
- **Shipped value:** `nomic-embed-text:latest`

Exact semantic model identity for discovery.

### `dimensions`

- **Type:** positive integer
- **Shipped value:** `768`

Required output vector dimensions.

### `profile_version`

- **Type:** version string
- **Shipped value:** `domain-discovery-v1`

Operator-controlled semantic cache/version identity.

This profile may share an endpoint and model with conversation memory, but it
does not read `[conversation_memory]` embedding settings. Provider, model,
dimensions, profile version, descriptor schema, registry version, and
descriptor digest participate in cache identity. If the semantic profile is
invalid or unavailable, discovery fails soft and ordinary dialogue continues.

## `[vector_db]`

Reserved settings for future persistent vector storage. They are not an active vector service contract.

### `granularity`

- **Type:** string
- **Shipped value:** `chunk_3`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** reserved

Reserved chunking mode for future vector storage.

**Example:** `granularity = chunk_3`

### `min_tokens`

- **Type:** integer
- **Shipped value:** `10`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** reserved

Configures min tokens for the `[vector_db]` subsystem.

**Example:** `min_tokens = 10`

### `skip_trivial`

- **Type:** boolean
- **Shipped value:** `yes`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** reserved

Configures skip trivial for the `[vector_db]` subsystem.

**Example:** `skip_trivial = yes`

### `max_size_gb`

- **Type:** integer
- **Shipped value:** `250`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** reserved

Configures max size gb for the `[vector_db]` subsystem.

**Example:** `max_size_gb = 250`

## `[logging]`

Runtime log formatting and severity settings.

### `log_stamping`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** `false`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures log stamping for the `[logging]` subsystem.

**Example:** `log_stamping = true`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `inc_stderr`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures inc stderr for the `[logging]` subsystem.

**Example:** `inc_stderr = true`

### `log_level`

- **Type:** string
- **Shipped value:** `DEBUG`
- **Runtime fallback:** `INFO`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `TRACE`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`
- **Status:** active

Sets the minimum runtime logging severity.

**Example:** `log_level = DEBUG`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `supplementary`

- **Type:** string
- **Shipped value:** `light-green`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures supplementary for the `[logging]` subsystem.

**Example:** `supplementary = light-green`

### `feature`

- **Type:** string
- **Shipped value:** `cyan`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures feature for the `[logging]` subsystem.

**Example:** `feature = cyan`

## `[openai_gateway]`

Reserved settings for a future OpenAI-compatible gateway.

### `enabled`

- **Type:** boolean
- **Shipped value:** `false`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** reserved

Configures enabled for the `[openai_gateway]` subsystem.

**Example:** `enabled = false`

### `host`

- **Type:** string
- **Shipped value:** `127.0.0.1`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** reserved

Configures host for the `[openai_gateway]` subsystem.

**Example:** `host = 127.0.0.1`

### `port`

- **Type:** integer
- **Shipped value:** `11435`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** reserved

Configures port for the `[openai_gateway]` subsystem.

**Example:** `port = 11435`

### `require_api_key`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** reserved

Configures require api key for the `[openai_gateway]` subsystem.

**Example:** `require_api_key = true`

### `api_key_env`

- **Type:** string
- **Shipped value:** `ORAC_OPENAI_GATEWAY_API_KEY`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** reserved

Configures api key env for the `[openai_gateway]` subsystem.

**Example:** `api_key_env = ORAC_OPENAI_GATEWAY_API_KEY`

## `[retrieval]`

Internet retrieval policy, evidence limits, caching, and response style.

### `internet_search_enabled`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Master switch for internet retrieval.

**Example:** `internet_search_enabled = true`

### `internet_search_mode`

- **Type:** string
- **Shipped value:** `explicit_only`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `disabled`, `explicit_only`, `suggest_search`, `auto_safe`
- **Status:** active

Controls when Orac may initiate internet retrieval.

**Example:** `internet_search_mode = explicit_only`

### `default_search_provider`

- **Type:** string
- **Shipped value:** `searxng`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Currently `searxng`
- **Status:** active

Selects the search provider used by retrieval.

**Example:** `default_search_provider = searxng`

### `max_search_results`

- **Type:** integer
- **Shipped value:** `5`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Maximum search results accepted from the provider.

**Example:** `max_search_results = 5`

### `max_sources_to_fetch`

- **Type:** integer
- **Shipped value:** `3`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Maximum result pages fetched as evidence.

**Example:** `max_sources_to_fetch = 3`

### `max_response_bytes`

- **Type:** integer
- **Shipped value:** `256000`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Maximum response body size accepted from a fetched source.

**Example:** `max_response_bytes = 256000`

### `max_redirects`

- **Type:** integer
- **Shipped value:** `3`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Maximum redirects followed while fetching a source.

**Example:** `max_redirects = 3`

### `cache_ttl_hours`

- **Type:** integer
- **Shipped value:** `12`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures cache ttl hours for the `[retrieval]` subsystem.

**Example:** `cache_ttl_hours = 12`

### `require_citations`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Requires retrieved answers to include source citations.

**Example:** `require_citations = true`

### `retrieval_response_style`

- **Type:** string
- **Shipped value:** `normal`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `concise`, `normal`, `detailed`
- **Status:** active

Controls the amount of retrieved detail in the final response.

**Example:** `retrieval_response_style = normal`

## `[retrieval.searxng]`

SearXNG endpoint and lifecycle settings.

### `base_url`

- **Type:** string
- **Shipped value:** `http://127.0.0.1:8888`
- **Runtime fallback:** `http://127.0.0.1:8080` in the controller loader
- **Required:** Yes when SearXNG retrieval is enabled
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Base HTTP URL for the component endpoint.

**Example:** `base_url = http://127.0.0.1:8888`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `autostart`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Allows stack tooling to activate the component's Compose profile.

**Example:** `autostart = true`

### `host`

- **Type:** string
- **Shipped value:** `127.0.0.1`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures host for the `[retrieval.searxng]` subsystem.

**Example:** `host = 127.0.0.1`

### `port`

- **Type:** integer
- **Shipped value:** `8888`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures port for the `[retrieval.searxng]` subsystem.

**Example:** `port = 8888`

### `timeout_seconds`

- **Type:** integer
- **Shipped value:** `10`
- **Runtime fallback:** `5` seconds in the controller loader
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures timeout seconds for the `[retrieval.searxng]` subsystem.

**Example:** `timeout_seconds = 10`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

## `[retrieval.person_facts]`

Source preference and corroboration policy for person facts.

### `prefer_wikidata`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures prefer wikidata for the `[retrieval.person_facts]` subsystem.

**Example:** `prefer_wikidata = true`

### `prefer_wikipedia`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures prefer wikipedia for the `[retrieval.person_facts]` subsystem.

**Example:** `prefer_wikipedia = true`

### `require_corroboration_for_recent_deaths`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Requires corroborating evidence for recent death claims.

**Example:** `require_corroboration_for_recent_deaths = true`

### `recent_death_days`

- **Type:** integer
- **Shipped value:** `90`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures recent death days for the `[retrieval.person_facts]` subsystem.

**Example:** `recent_death_days = 90`

## `[knowledge]`

Core knowledge ingestion, managed content storage, chunking, and embedding
settings. See [Document Ingestion](document-ingestion.md) for the end-to-end
ownership, APEX administration, lifecycle, and security model.

### `enabled`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** `true`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Enables the Core-owned knowledge ingestion worker service.

**Example:** `enabled = true`

### `managed_root`

- **Type:** path/string
- **Shipped value:** `${ORAC_HOME}/var/knowledge/content`
- **Runtime fallback:** `${ORAC_HOME}/var/knowledge/content`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** A local, non-symlink directory owned by the Core runtime
- **Status:** active

Root directory for the Core-managed content-addressed pool shared by raw and
normalised payloads. The store creates a missing root as `0750`, uses `0700`
for `.tmp`, creates shard directories as `0750`, and writes immutable objects
as `0600`. It applies those modes explicitly after creation so the process
umask cannot widen them. Existing directories must be runtime-owned and must
not be group- or other-writable; existing objects must be runtime-owned,
regular, non-symlink files with no group, other, or execute permissions.

The configured root itself may be created but may not be a symlink. Store
initialisation verifies that `.tmp` and `sha256` are on the same filesystem and
that no-replace hard-link promotion is supported. It fails closed with stable
configuration reason codes when root identity, ownership, permissions,
filesystem compatibility, or promotion capability is unsafe. Capture and
worker instances fix the resolved root and its device/inode identity for their
lifetime, so changing this setting requires service/store reinitialisation.

**Example:** `managed_root = ${ORAC_HOME}/var/knowledge/content`

### `request_lease_seconds`

- **Type:** integer
- **Shipped value:** `300`
- **Runtime fallback:** `300`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Positive integer seconds
- **Status:** active

Lease duration for a worker-claimed ingestion request.

**Example:** `request_lease_seconds = 300`

### `batch_size`

- **Type:** integer
- **Shipped value:** `5`
- **Runtime fallback:** `5`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Positive integer
- **Status:** active

Maximum number of knowledge ingestion requests processed per worker tick. Each
request is claimed and processed under its own transaction and error boundary.

**Example:** `batch_size = 5`

### `chunk_size_tokens`

- **Type:** integer
- **Shipped value:** `1536`
- **Runtime fallback:** `1536`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Positive integer token estimate
- **Status:** active

Target conservative input-accounting size used when chunking extracted
knowledge text. The production counter uses UTF-8 bytes as a safe upper bound
for BERT-family non-special tokens; `1536` bytes is approximately the former
384-token prose target while remaining safe for punctuation-heavy and
low-whitespace input.

**Example:** `chunk_size_tokens = 1536`

### `chunk_overlap_tokens`

- **Type:** integer
- **Shipped value:** `192`
- **Runtime fallback:** `192`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Non-negative integer smaller than `chunk_size_tokens`
- **Status:** active

Overlap retained between adjacent knowledge chunks.

**Example:** `chunk_overlap_tokens = 192`

Knowledge embedding identity is not configured in this ingestion section.
Production ingestion and retrieval use the dedicated immutable
`[embedding.knowledge]` profile below. There is no profile-less or hash-backed
production knowledge path.

## `[embedding.knowledge]`

Purpose-isolated production profile for knowledge chunk embeddings. The shipped
profile uses local Ollama Nomic embeddings, Nomic's retrieval prefixes,
`truncate=false`, and native Oracle `VECTOR(768,FLOAT32)` storage. It does not
share activation or cache lifecycle with `[embedding.domain_discovery]`.

| Key | Shipped value | Contract |
|---|---|---|
| `provider` | `ollama` | Production semantic provider; deterministic hash providers are rejected. |
| `service_url` | `http://127.0.0.1:11434` | Trusted local Ollama endpoint. |
| `model_id` | `nomic-embed-text:latest` | Callable local model tag. |
| `model_digest` | `0a109f...e59f` | Full resolved immutable digest; a mismatch fails closed. |
| `dimensions` | `768` | Must match the fixed native vector column. |
| `profile_version` | `knowledge-v1` | Immutable logical identity; change it for any digest, transform, or policy change. |
| `document_input_prefix` | `search_document:` | Nomic document-mode transform. |
| `query_input_prefix` | `search_query:` | Nomic query-mode transform. |
| `truncate` | `false` | Oversized inputs fail rather than silently changing their semantic content. |
| `request_batch_size` | `2` | Operational Ollama request split; does not change vector identity. |
| `model_context_tokens` | `2048` | Must exactly match the context reported by the resolved local model. |
| `context_safety_margin_tokens` | `64` | Reserved from the model maximum before prefix and content accounting. |
| `retrieval_policy_version` | `knowledge-hybrid-v1` | Deterministic hybrid policy identity. |
| `semantic_threshold` | `0.60` | Initial calibration only for this pinned digest and input transform; not a universal embedding threshold. |

The resolved digest, purpose, model, dimensions, prefixes, truncation policy,
profile version, and retrieval policy are persisted as one immutable database
profile. Changing the model behind `latest` without updating the configured
digest fails before retrieval. A real profile change requires a new
`profile_version`, native re-embedding, validation, and atomic activation.

### `provider`

Production provider code. Shipped and supported value: `ollama`.

### `service_url`

Trusted local Ollama base URL. Shipped value: `http://127.0.0.1:11434`.

### `model_id`

Callable model tag. Shipped value: `nomic-embed-text:latest`.

### `model_digest`

Full immutable digest resolved from the local Ollama catalogue. A mismatch
fails closed; updating it requires a new profile version and rebuild.

### `dimensions`

Fixed vector dimension count. Shipped and supported value: `768`.

### `profile_version`

Immutable purpose-specific lifecycle identity. Shipped value: `knowledge-v1`.

### `document_input_prefix`

Nomic document-mode prefix. Shipped value: `search_document:`.

### `query_input_prefix`

Nomic query-mode prefix. Shipped value: `search_query:`.

### `truncate`

Must remain `false`; oversized text fails visibly instead of being truncated.

### `request_batch_size`

Maximum inputs per local Ollama request. Shipped value: `2`; larger ingestion
batches are split without changing profile or vector identity.

### `model_context_tokens`

Configured model maximum. The shipped Nomic model reports `2048` through
Ollama `/api/show`; startup fails if the configured and resolved values differ.

### `context_safety_margin_tokens`

Reserved input headroom. The shipped value is `64`, leaving a usable ceiling
of `1984` before the `search_document:` or `search_query:` prefix, model
special tokens, and content are charged. The local provider rejects an input
with `EMBEDDING_INPUT_CONTEXT_EXCEEDED` before calling `/api/embed` when its
conservative estimate exceeds that ceiling. `truncate` remains `false`.

### `retrieval_policy_version`

Immutable host/database ranking contract. Shipped value:
`knowledge-hybrid-v1`.

### `semantic_threshold`

Shipped value: `0.60`. This is profile-specific calibration for the exact
Nomic digest and input transform, not a universal semantic threshold.

## `[knowledge.reconciliation]`

Strictly read-only operational inventory limits for
`bin/orac-knowledge.sh reconcile`. Hitting any scan ceiling returns
`INCOMPLETE`; it never produces `READY`. CLI overrides may lower, but cannot
raise, the shipped ceilings. See
[Knowledge Storage Maintenance](knowledge-maintenance.md#read-only-operational-reconciliation)
for result semantics, redaction, concurrency, and the separate-authorisation
boundary for any future recovery action.

### `max_database_rows`

- **Type:** integer
- **Shipped value:** `250000`
- **Runtime fallback:** `250000`
- **Allowed values:** `2` to `1000000`
- **Status:** active

Maximum combined rows retained across the two short Oracle read-only
snapshots. Half of the limit is reserved for each snapshot.

### `max_filesystem_entries`

- **Type:** integer
- **Shipped value:** `250000`
- **Runtime fallback:** `250000`
- **Allowed values:** `1` to `1000000`
- **Status:** active

Maximum physical entries enumerated without following symbolic links.

### `max_hashed_bytes`

- **Type:** integer
- **Shipped value:** `10737418240`
- **Runtime fallback:** `10737418240`
- **Allowed values:** `1` to `107374182400`
- **Status:** active

Maximum bytes read through verified descriptors for object and bounded
temporary-file hashing.

### `max_temporary_files_hashed`

- **Type:** integer
- **Shipped value:** `1000`
- **Runtime fallback:** `1000`
- **Allowed values:** `1` to `10000`
- **Status:** active

Independent maximum number of temporary regular files hashed per scan.

### `max_elapsed_seconds`

- **Type:** integer
- **Shipped value:** `300`
- **Runtime fallback:** `300`
- **Allowed values:** `1` to `1800`
- **Status:** active

Maximum elapsed time for bounded physical enumeration and hashing.

### `max_report_items_per_reason`

- **Type:** integer
- **Shipped value:** `20`
- **Runtime fallback:** `20`
- **Allowed values:** `1` to `100`
- **Status:** active

Maximum sampled numeric database identities retained for each reason code.
Physical names and identities are never sampled.

### `max_report_bytes`

- **Type:** integer
- **Shipped value:** `1048576`
- **Runtime fallback:** `1048576`
- **Allowed values:** `512` to `4194304`
- **Status:** active

Maximum UTF-8 JSON report size. Samples are removed deterministically before a
minimal `RECON_REPORT_BYTE_LIMIT_EXCEEDED` result is returned.

### `stale_temporary_age_seconds`

- **Type:** integer
- **Shipped value:** `86400`
- **Runtime fallback:** `86400`
- **Allowed values:** Positive integer seconds
- **Status:** active

Minimum unchanged temporary-file age classified as stale. Reconciliation only
reports the entry; it does not remove or quarantine it.

### `unregistered_object_grace_seconds`

- **Type:** integer
- **Shipped value:** `86400`
- **Runtime fallback:** `86400`
- **Allowed values:** Positive integer seconds
- **Status:** active

Minimum age before a verified object absent from both database snapshots can
be classified as an orphan. Younger objects produce `INCOMPLETE` and a safe
retry reason.

### `concurrency`

- **Type:** integer
- **Shipped value:** `1`
- **Runtime fallback:** `1`
- **Allowed values:** `1`
- **Status:** active

Fixed single-threaded traversal for deterministic accounting and bounded I/O.

## `[knowledge.dialogue]`

The Core database install seeds the canonical `ORAC_CORE` project and its
relational knowledge scope. Additional projects remain administrator-managed
through `orac_code.project_registry_api`, and no project is inferred from Drop
Box configuration. See [Dialogue Routing](dialogue-routing.md).

This section controls dialogue retrieval from completed searchable content. It
does not enable document ingestion; that worker is controlled by
`[knowledge].enabled`.

Authenticated, scope-isolated local-knowledge retrieval during normal dialogue.
The shipped feature switch is `true`. Retrieval still requires accepted,
searchable documents and a current Oracle `USE` privilege for the authenticated
principal and canonical scope.

| Key | Shipped value | Contract |
|---|---|---|
| `enabled` | `true` | Enables dialogue retrieval; ingestion remains controlled by `[knowledge].enabled`. |
| `scope_aliases_json` | `{"orac":"PROJECT:ORAC_CORE","orac core":"PROJECT:ORAC_CORE","drop box":"PLUGIN:drop_box"}` | JSON object mapping case-insensitive dialogue aliases to canonical scopes. Unknown or ambiguous aliases do not retrieve. |
| `registry_cache_ttl_seconds` | `30` | Positive lifetime for active-scope registry snapshots. An expired refresh failure denies retrieval rather than serving stale eligibility. |
| `max_scopes_per_request` | `3` | Maximum requested canonical scopes. The first vertical slice routes one explicit scope. |
| `max_candidate_chunks_per_scope` | `100` | Hard cap on the bounded union of up to 50 semantic and 50 lexical candidates. |
| `max_selected_chunks` | `6` | Maximum chunks injected into one prompt. |
| `max_context_chars` | `12000` | Total local evidence character budget. |
| `max_chunk_chars` | `2200` | Per-chunk evidence character budget. |
| `min_lexical_score` | `0.25` | Compatibility setting for the independent lexical branch; it is not a semantic hard gate. |

### `enabled`

Boolean master switch for local-knowledge dialogue retrieval. The shipped value
is `true`; the runtime fallback remains `false` when the setting is absent.
Set it explicitly to `false` to disable dialogue retrieval.

### `scope_aliases_json`

JSON object mapping case-insensitive dialogue aliases to canonical scopes.
Aliases participate in deterministic explicit and implicit turn matching; they
do not grant access. See
[Local Knowledge Turn Triggers](dialogue-routing.md#local-knowledge-turn-triggers)
for the exact grammar, recognised expressions, and examples.

### `registry_cache_ttl_seconds`

Positive active-scope registry cache lifetime in seconds. Shipped value: `30`.

### `max_scopes_per_request`

Positive cap on canonical scopes requested in one turn. Shipped value: `3`.

### `max_candidate_chunks_per_scope`

Hard candidate-union cap per scope. Shipped value: `100`.

### `max_selected_chunks`

Maximum selected evidence chunks. Shipped value: `6`.

### `max_context_chars`

Total local evidence character budget. Shipped value: `12000`.

### `max_chunk_chars`

Per-chunk evidence character budget. Shipped value: `2200`.

### `min_lexical_score`

Inclusive lexical-branch relevance threshold from `0.0` to `1.0`. Shipped
value: `0.25`. It never excludes an independently admitted semantic candidate.
Generic route-selection words and canonical scope-name words are not counted
as topical lexical matches.

Environment overrides use the existing form, for example
`ORAC__KNOWLEDGE.DIALOGUE__ENABLED=false`. Malformed JSON, duplicate object keys,
registry unavailability, inactive scopes, and unauthorised users fail closed.
Denied and unavailable explicit knowledge requests terminate with safe,
non-disclosing responses; they do not fall through to plugins or an LLM.
See [Dialogue Routing](dialogue-routing.md).

`allow_all_scopes` and `user_scope_allowlist_json` are retired settings. Their
presence is a startup error. Every chunk or normalised-content retrieval must
have a current Oracle `USE` privilege.

## `[knowledge.retrieval]`

Controls the bounded P1-06 normalised-content materialisation service. These
limits do not widen the smaller dialogue grounding budgets.

### `enabled`

Feature switch for whole-document and selected-member materialisation. Shipped
value: `true`. Authorised chunk search remains controlled by
`[knowledge.dialogue].enabled`.

### `max_metadata_members`

Maximum member descriptors returned by one metadata request. Shipped and hard
maximum: `256`.

### `max_selected_members`

Maximum explicitly selected artefact members. Shipped and hard maximum: `32`.

### `max_selected_chunks`

Maximum chunks in an identity-bounded chunk or section range. Shipped and hard
maximum: `64`.

### `max_table_rows`

Maximum CSV rows in one table-range result. Shipped and hard maximum: `10000`.

### `max_member_source_bytes`

Maximum registered source size for one materialised member. Shipped and hard
maximum: `8388608` bytes.

### `max_aggregate_source_bytes`

Maximum aggregate registered source size inspected for one request. Shipped
and hard maximum: `16777216` bytes.

### `max_emitted_bytes`

Maximum bytes emitted by one materialisation request. Shipped and hard maximum:
`4194304` bytes. Oversized results fail rather than truncate.

### `stream_block_bytes`

Maximum response iteration block size. Shipped and hard maximum: `1048576`
bytes.

## `[knowledge.materialisation]`

Controls the P1-07 progressive normalised materialisation policy above P1-06.
It never enables raw binary routing and does not connect the result to an LLM.

### `enabled`

Feature switch for P1-07. Shipped value: `true`. It has no effect unless
`[knowledge.retrieval].enabled=true`.

### `token_safety_margin_percent`

Safety margin added to the conservative UTF-8 token estimate. Shipped value:
`20`.

### `max_complete_bytes`

Maximum verified bytes for a complete normalised document. Shipped value:
`262144`; it cannot exceed the P1-06 emitted-byte ceiling.

### `max_complete_tokens`

Maximum safety-adjusted evidence tokens for a complete document. Shipped value:
`12000`.

### `max_complete_context_percent`

Maximum percentage of currently usable model input context occupied by a
complete document. Shipped value: `25`.

### `max_surrounding_chunks_each_side`

Maximum surrounding chunks selected before and after controlled anchors.
Shipped value: `2`; the immutable retrieval-envelope ceiling is `8`.

### `local_only_broad_materialisation`

Restricts levels broader than relevant chunks to explicitly local processing.
Shipped value: `true`.

### `classification_enforcement_enabled`

Enables an approved classification-to-locality policy mapping. Shipped value:
`false`; current `DOC_CLASS` codes are descriptive only.

### `truncation_permitted`

Reserved fail-closed setting. Shipped and only accepted P1-07 value: `false`.
P1-07 downgrades or rejects instead of truncating.

## `[knowledge.binary_materialisation]`

Controls the internal P2-06 secure attachment boundary. It does not enable
routing, register a processor, invoke a provider, or alter the Phase 1
prompt-only path. The shipped runtime has an empty processor registry and a
fail-closed route revalidator, so changing configuration alone cannot make a
binary route eligible.

### `enabled`

Shipped value: `false`. When `true`, initialises the private attachment store
and bounded startup reconciliation. Materialisation still `DEFER`s unless an
exact separately reviewed P2-05 route revalidator and deterministic processor
profile are registered in code.

### `runtime_root`

Host-owned private attachment runtime directory. Shipped value:
`${ORAC_HOME}/var/knowledge/attachments`. The service requires an owner-only
mode-`0700` directory, stores payload/metadata files as mode `0600`, and never
returns this path to callers.

### `max_source_bytes`

Host ceiling for one registered source. Shipped value: `16777216`. The smaller
P2-04/P2-05 approved `BYTES` limit remains authoritative.

### `max_output_bytes`

Host ceiling for one materialised attachment. Shipped value: `16777216`. The
smaller approved `OUTPUT_BYTES` limit remains authoritative.

### `max_elapsed_seconds`

Host ceiling for deterministic inspection and materialisation. Shipped value:
`30`. The smaller approved `ELAPSED_TIME` limit remains authoritative.

### `max_ttl_seconds`

Maximum lifetime of an opaque unconsumed handle. Shipped value: `300`.

### `max_cleanup_grace_seconds`

Maximum interval between handle expiry and its required cleanup deadline.
Shipped value: `60`.

### `max_recovery_entries`

Maximum runtime-root entries inspected by one startup or shutdown recovery
pass. Shipped value: `4096`.

### `max_recovery_elapsed_seconds`

Maximum elapsed time for one reconciliation pass. Shipped value: `10`.

### `stale_allocation_seconds`

Minimum age before an exact owner-controlled temporary allocation layout may be
removed during reconciliation. Shipped value: `300`. Unknown or ambiguous
entries are reported and retained.

## `[knowledge.model_evidence]`

Controls the P1-08 canonical text-evidence submission layer. It has no effect
unless `[knowledge.dialogue].enabled`, `[knowledge.retrieval].enabled`, and
`[knowledge.materialisation].enabled` are also true. See
[Knowledge Model Evidence Submission](knowledge-model-evidence.md).

### `enabled`

Shipped value: `true`. Enables eligible approved evidence submission to the
primary local text adapter.

### `shadow_mode`

Shipped value: `false`. Runs envelope and budget diagnostics without recording
a submission decision or invoking with materialised evidence.

### `envelope_version`

Shipped and only accepted value: `1`.

### `reserved_output_tokens`

Shipped and only accepted value: `2048`. This is both the fixed output reserve
and the strict adapter output cap.

### `context_safety_percent`

Shipped value: `5`. Percentage of registered context reserved as an additional
final-prompt safety margin.

### `context_safety_min_tokens`

Shipped value: `256`. Minimum additional context safety margin.

### `max_evidence_context_percent`

Shipped value: `25`. Maximum percentage of usable input occupied by the exact
rendered envelope.

### `min_effective_context_tokens`

Shipped value: `32768`. P1-08 is eligible only when the lower of the governed
registry context ceiling and any observed provider runtime ceiling meets this
floor. When runtime capacity cannot be observed, Core uses the governed
registry ceiling and emits a safe warning. A model below the floor bypasses
P1-07/P1-08 for that turn; existing bounded RAG remains available.

### `classification_enforcement_enabled`

Shipped value: `true`. Enables the P1-08 classification gate when the feature
itself is enabled.

### `local_text_models_only`

Shipped value: `true`. Requires an explicitly local,
text-evidence-eligible provider capability.

### `follow_up_enabled`

Shipped value: `false`. Enables registered same-document follow-up state after
initial rollout.

### `follow_up_max_rounds`

Shipped value: `2`. Maximum follow-up rounds after the initial evidence turn.

### `follow_up_max_bytes`

Shipped value: `524288`. Cumulative rendered-envelope byte ceiling.

### `follow_up_max_tokens`

Shipped value: `24000`. Cumulative conservative evidence-token ceiling.

### `follow_up_max_members`

Shipped value: `16`. Cumulative selected-member ceiling.

### `follow_up_max_chunks`

Shipped value: `64`. Cumulative selected-chunk ceiling.

### `follow_up_max_rows`

Shipped value: `2000`. Cumulative emitted CSV-row ceiling.

### `follow_up_max_elapsed_seconds`

Shipped value: `120`. Expiry measured from the initial evidence turn.

### `pre_output_retry_count`

Shipped and only accepted value: `1`. This permits one transient retry before
any model output.

`MAX_CONTEXT_TOKENS` must be a current positive value on the exact enabled
registry row. When the selected connector reports its active runtime limit,
Core uses the smaller registry/runtime value for P1-07 and the final P1-08
budget check. A row-version or runtime-observation change forces a fresh P1-07
decision. The provider must declare `processing_locality=LOCAL` and
`text_evidence_eligible=true`; locality is never inferred from a service URL.
Prompt dumps are disabled for an evidence turn regardless of the general
context dump settings.

## `[display]`

Optional local display event transport.

### `enabled`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** `false`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures enabled for the `[display]` subsystem.

**Example:** `enabled = true`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `auto_start`

- **Type:** boolean
- **Shipped value:** `false`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures auto start for the `[display]` subsystem.

**Example:** `auto_start = false`

### `host`

- **Type:** string
- **Shipped value:** `127.0.0.1`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures host for the `[display]` subsystem.

**Example:** `host = 127.0.0.1`

### `port`

- **Type:** integer
- **Shipped value:** `8766`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures port for the `[display]` subsystem.

**Example:** `port = 8766`

### `state_file`

- **Type:** path/string
- **Shipped value:** `${ORAC_HOME}/var/tmp/orac_display_state.json`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Path to the latest display-state recovery file.

**Example:** `state_file = ${ORAC_HOME}/var/tmp/orac_display_state.json`

### `connect_timeout_seconds`

- **Type:** number
- **Shipped value:** `0.05`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures connect timeout seconds for the `[display]` subsystem.

**Example:** `connect_timeout_seconds = 0.05`

## `[voice]`

Activation, capture, STT, TTS, playback, interruption, and AEC settings.

### `enabled`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** `false`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures enabled for the `[voice]` subsystem.

**Example:** `enabled = true`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `mode`

- **Type:** string
- **Shipped value:** `local`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Currently `local`
- **Status:** active

Configures mode for the `[voice]` subsystem.

**Example:** `mode = local`

### `activation_mode`

- **Type:** string
- **Shipped value:** `openwakeword`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `openwakeword`, `enter`, `stt_phrase`, `porcupine`
- **Status:** active

Selects manual or wake-word activation behavior.

**Example:** `activation_mode = openwakeword`

### `wake_engine`

- **Type:** string
- **Shipped value:** `openwakeword`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `openwakeword`, `stt_phrase`, `porcupine`
- **Status:** active

Selects the wake detection backend.

**Example:** `wake_engine = openwakeword`

### `wake_phrase`

- **Type:** string
- **Shipped value:** `Hey Orac`
- **Runtime fallback:** `orac`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures wake phrase for the `[voice]` subsystem.

**Example:** `wake_phrase = Hey Orac`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `wake_model`

- **Type:** string
- **Shipped value:** _empty_
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; empty disables or defers the optional value
- **Allowed values:** Any value valid for the described subsystem
- **Status:** optional

Configures wake model for the `[voice]` subsystem.

**Example:** `wake_model = `

### `wake_threshold`

- **Type:** number
- **Shipped value:** `0.75`
- **Runtime fallback:** `0.6`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures wake threshold for the `[voice]` subsystem.

**Example:** `wake_threshold = 0.75`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `wake_listen_sample_rate`

- **Type:** integer
- **Shipped value:** `16000`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures wake listen sample rate for the `[voice]` subsystem.

**Example:** `wake_listen_sample_rate = 16000`

### `wake_chunk_ms`

- **Type:** integer
- **Shipped value:** `80`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures wake chunk ms for the `[voice]` subsystem.

**Example:** `wake_chunk_ms = 80`

### `wake_rearm_seconds`

- **Type:** number
- **Shipped value:** `0.2`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures wake rearm seconds for the `[voice]` subsystem.

**Example:** `wake_rearm_seconds = 0.2`

### `wake_capture_delay_seconds`

- **Type:** number
- **Shipped value:** `0.1`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures wake capture delay seconds for the `[voice]` subsystem.

**Example:** `wake_capture_delay_seconds = 0.1`

### `console_timestamps`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures console timestamps for the `[voice]` subsystem.

**Example:** `console_timestamps = true`

### `openwakeword_model_paths`

- **Type:** path/string
- **Shipped value:** _empty_
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; empty disables or defers the optional value
- **Allowed values:** Any value valid for the described subsystem
- **Status:** optional

Comma-separated explicit openWakeWord model paths.

**Example:** `openwakeword_model_paths = `

### `openwakeword_model_names`

- **Type:** comma-separated string list
- **Shipped value:** `hey_orac`
- **Runtime fallback:** `hey_jarvis`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Comma-separated openWakeWord built-in or bare model names.

**Example:** `openwakeword_model_names = hey_orac`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `openwakeword_model_dirs`

- **Type:** path/string
- **Shipped value:** _empty_
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; empty disables or defers the optional value
- **Allowed values:** Any value valid for the described subsystem
- **Status:** optional

Comma-separated directories searched for bare model names.

**Example:** `openwakeword_model_dirs = `

### `openwakeword_threshold`

- **Type:** number
- **Shipped value:** `0.75`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures openwakeword threshold for the `[voice]` subsystem.

**Example:** `openwakeword_threshold = 0.75`

### `openwakeword_inference_framework`

- **Type:** string
- **Shipped value:** `auto`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures openwakeword inference framework for the `[voice]` subsystem.

**Example:** `openwakeword_inference_framework = auto`

### `openwakeword_refractory_seconds`

- **Type:** number
- **Shipped value:** `0.2`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures openwakeword refractory seconds for the `[voice]` subsystem.

**Example:** `openwakeword_refractory_seconds = 0.2`

### `porcupine_keyword_path`

- **Type:** path/string
- **Shipped value:** _empty_
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; empty disables or defers the optional value
- **Allowed values:** Any value valid for the described subsystem
- **Status:** optional

Configures porcupine keyword path for the `[voice]` subsystem.

**Example:** `porcupine_keyword_path = `

### `porcupine_builtin_keyword`

- **Type:** string
- **Shipped value:** `porcupine`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures porcupine builtin keyword for the `[voice]` subsystem.

**Example:** `porcupine_builtin_keyword = porcupine`

### `porcupine_sensitivity`

- **Type:** number
- **Shipped value:** `0.6`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures porcupine sensitivity for the `[voice]` subsystem.

**Example:** `porcupine_sensitivity = 0.6`

### `porcupine_access_key_resource`

- **Type:** string
- **Shipped value:** `picovoice/access_key`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Encrypted API-key-store resource containing the Picovoice access key.

**Example:** `porcupine_access_key_resource = picovoice/access_key`

### `stt_phrase_enabled`

- **Type:** boolean
- **Shipped value:** `false`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures stt phrase enabled for the `[voice]` subsystem.

**Example:** `stt_phrase_enabled = false`

### `tts_engine`

- **Type:** string
- **Shipped value:** `kokoro`
- **Runtime fallback:** `piper`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `kokoro`, `piper`
- **Status:** active

Selects the primary text-to-speech backend.

**Example:** `tts_engine = kokoro`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `tts_fallback_engine`

- **Type:** string
- **Shipped value:** `piper`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `piper` or empty
- **Status:** active

Selects the backend used when primary synthesis fails.

**Example:** `tts_fallback_engine = piper`

### `tts_voice`

- **Type:** string
- **Shipped value:** `en_GB-alba-medium`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures the legacy Piper voice and the Piper fallback voice. Runtime
`tts_voice` preferences resolve through the TTS voice catalogue; when the
primary engine is Kokoro, `tts_kokoro_voice` is the configured engine voice.

**Example:** `tts_voice = en_GB-alba-medium`

**Notes:** Runtime voice selection is documented in
[Runtime User Preferences](user_preferences.md).

### `tts_voice_dir`

- **Type:** path/string
- **Shipped value:** `${ORAC_HOME}/var/models/piper`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures tts voice dir for the `[voice]` subsystem.

**Example:** `tts_voice_dir = ${ORAC_HOME}/var/models/piper`

### `tts_kokoro_autostart`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures tts kokoro autostart for the `[voice]` subsystem.

**Example:** `tts_kokoro_autostart = true`

### `tts_kokoro_runtime`

- **Type:** string
- **Shipped value:** `docker-cpu`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `docker-cpu`, `docker-gpu`, `external`
- **Status:** active

Selects managed CPU, managed GPU, or external Kokoro operation.

**Example:** `tts_kokoro_runtime = docker-cpu`

### `tts_kokoro_container_name`

- **Type:** string
- **Shipped value:** `orac-kokoro`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures tts kokoro container name for the `[voice]` subsystem.

**Example:** `tts_kokoro_container_name = orac-kokoro`

### `tts_kokoro_host`

- **Type:** string
- **Shipped value:** `127.0.0.1`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures tts kokoro host for the `[voice]` subsystem.

**Example:** `tts_kokoro_host = 127.0.0.1`

### `tts_kokoro_port`

- **Type:** integer
- **Shipped value:** `8880`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures tts kokoro port for the `[voice]` subsystem.

**Example:** `tts_kokoro_port = 8880`

### `tts_kokoro_base_url`

- **Type:** string
- **Shipped value:** `http://127.0.0.1:8880/v1`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** Yes when Kokoro is selected
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures tts kokoro base url for the `[voice]` subsystem.

**Example:** `tts_kokoro_base_url = http://127.0.0.1:8880/v1`

### `tts_kokoro_image`

- **Type:** string
- **Shipped value:** _empty_
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; empty disables or defers the optional value
- **Allowed values:** Any value valid for the described subsystem
- **Status:** optional

Configures tts kokoro image for the `[voice]` subsystem.

**Example:** `tts_kokoro_image = `

### `tts_kokoro_model`

- **Type:** string
- **Shipped value:** `kokoro`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures tts kokoro model for the `[voice]` subsystem.

**Example:** `tts_kokoro_model = kokoro`

### `tts_kokoro_voice`

- **Type:** string
- **Shipped value:** `bm_george`
- **Runtime fallback:** `af_heart`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures the Kokoro voice used by the Kokoro engine and the Kokoro voice
catalogue fallback.

**Example:** `tts_kokoro_voice = bm_george`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `tts_kokoro_response_format`

- **Type:** string
- **Shipped value:** `wav`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures tts kokoro response format for the `[voice]` subsystem.

**Example:** `tts_kokoro_response_format = wav`

### `tts_kokoro_timeout_seconds`

- **Type:** integer
- **Shipped value:** `60`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures tts kokoro timeout seconds for the `[voice]` subsystem.

**Example:** `tts_kokoro_timeout_seconds = 60`

### `tts_kokoro_api_key_env`

- **Type:** string
- **Shipped value:** _empty_
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; empty disables or defers the optional value
- **Allowed values:** Any value valid for the described subsystem
- **Status:** optional

Configures tts kokoro api key env for the `[voice]` subsystem.

**Example:** `tts_kokoro_api_key_env = `

### `tts_kokoro_final_fade_ms`

- **Type:** integer
- **Shipped value:** `8`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures tts kokoro final fade ms for the `[voice]` subsystem.

**Example:** `tts_kokoro_final_fade_ms = 8`

### `tts_kokoro_gain_db`

- **Type:** number
- **Shipped value:** `10.0`
- **Runtime fallback:** `0.0`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures tts kokoro gain db for the `[voice]` subsystem.

**Example:** `tts_kokoro_gain_db = 10.0`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `tts_kokoro_debug_audio`

- **Type:** boolean
- **Shipped value:** `false`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures tts kokoro debug audio for the `[voice]` subsystem.

**Example:** `tts_kokoro_debug_audio = false`

### `tts_kokoro_retain_raw_response`

- **Type:** boolean
- **Shipped value:** `false`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures tts kokoro retain raw response for the `[voice]` subsystem.

**Example:** `tts_kokoro_retain_raw_response = false`

### `playback_backend`

- **Type:** string
- **Shipped value:** `shell`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `shell`, `native`
- **Status:** experimental

Selects shell-command playback or experimental native PCM playback.

**Example:** `playback_backend = shell`

### `playback_frame_ms`

- **Type:** integer
- **Shipped value:** `10`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures playback frame ms for the `[voice]` subsystem.

**Example:** `playback_frame_ms = 10`

### `aec_backend`

- **Type:** string
- **Shipped value:** `null`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `null`, `livekit`
- **Status:** experimental

Selects pass-through or LiveKit acoustic echo cancellation.

**Example:** `aec_backend = null`

### `aec_stream_delay_ms`

- **Type:** integer
- **Shipped value:** `0`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** experimental

Configures aec stream delay ms for the `[voice]` subsystem.

**Example:** `aec_stream_delay_ms = 0`

### `tts_coalesce_enabled`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Configures tts coalesce enabled for the `[voice]` subsystem.

**Example:** `tts_coalesce_enabled = true`

### `tts_coalesce_max_chars`

- **Type:** integer
- **Shipped value:** `320`
- **Runtime fallback:** `220`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures tts coalesce max chars for the `[voice]` subsystem.

**Example:** `tts_coalesce_max_chars = 320`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `tts_coalesce_min_chunks`

- **Type:** integer
- **Shipped value:** `4`
- **Runtime fallback:** `2`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures tts coalesce min chunks for the `[voice]` subsystem.

**Example:** `tts_coalesce_min_chunks = 4`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `enable_experimental_barge_in`

- **Type:** boolean
- **Shipped value:** `false`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** experimental

Master acknowledgement switch for experimental interruption handling.

**Example:** `enable_experimental_barge_in = false`

### `barge_in_mode`

- **Type:** string
- **Shipped value:** `wakeword`
- **Runtime fallback:** `vad`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `wakeword`, `openwakeword`, `vad`, `stt_phrase`
- **Status:** experimental

Selects wake-word or VAD-based interruption detection.

**Example:** `barge_in_mode = wakeword`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `barge_in_min_speech_ms`

- **Type:** integer
- **Shipped value:** `250`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** experimental

Configures barge in min speech ms for the `[voice]` subsystem.

**Example:** `barge_in_min_speech_ms = 250`

### `barge_in_grace_ms`

- **Type:** integer
- **Shipped value:** `500`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** experimental

Configures barge in grace ms for the `[voice]` subsystem.

**Example:** `barge_in_grace_ms = 500`

### `barge_in_cooldown_ms`

- **Type:** integer
- **Shipped value:** `1000`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** experimental

Configures barge in cooldown ms for the `[voice]` subsystem.

**Example:** `barge_in_cooldown_ms = 1000`

### `barge_in_return_mode`

- **Type:** string
- **Shipped value:** `wake_listening`
- **Runtime fallback:** `command_capture`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `wake_listening`, `command_capture`
- **Status:** experimental

Configures barge in return mode for the `[voice]` subsystem.

**Example:** `barge_in_return_mode = wake_listening`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `barge_in_ignore_during_tts_start_ms`

- **Type:** integer
- **Shipped value:** `300`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** experimental

Configures barge in ignore during tts start ms for the `[voice]` subsystem.

**Example:** `barge_in_ignore_during_tts_start_ms = 300`

### `barge_in_post_response_ms`

- **Type:** integer
- **Shipped value:** `12000`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** experimental

Configures barge in post response ms for the `[voice]` subsystem.

**Example:** `barge_in_post_response_ms = 12000`

### `barge_in_post_response_cancel_enabled`

- **Type:** boolean
- **Shipped value:** `false`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** experimental

Configures barge in post response cancel enabled for the `[voice]` subsystem.

**Example:** `barge_in_post_response_cancel_enabled = false`

### `stt_engine`

- **Type:** string
- **Shipped value:** `faster_whisper`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Currently `faster_whisper`
- **Status:** active

Selects the speech-to-text backend.

**Example:** `stt_engine = faster_whisper`

### `stt_model`

- **Type:** string
- **Shipped value:** `small.en`
- **Runtime fallback:** `base.en`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Faster Whisper model identifier or local path.

**Example:** `stt_model = small.en`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `stt_device`

- **Type:** string
- **Shipped value:** `cpu`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures stt device for the `[voice]` subsystem.

**Example:** `stt_device = cpu`

### `stt_compute_type`

- **Type:** string
- **Shipped value:** `int8`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures stt compute type for the `[voice]` subsystem.

**Example:** `stt_compute_type = int8`

### `stt_record_mode`

- **Type:** string
- **Shipped value:** `vad`
- **Runtime fallback:** `fixed`
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `fixed`, `vad`
- **Status:** active

Selects fixed-duration or VAD-controlled recording.

**Example:** `stt_record_mode = vad`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `stt_record_seconds`

- **Type:** integer
- **Shipped value:** `5`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures stt record seconds for the `[voice]` subsystem.

**Example:** `stt_record_seconds = 5`

### `stt_max_record_seconds`

- **Type:** integer
- **Shipped value:** `20`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures stt max record seconds for the `[voice]` subsystem.

**Example:** `stt_max_record_seconds = 20`

### `stt_min_record_seconds`

- **Type:** number
- **Shipped value:** `0.8`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures stt min record seconds for the `[voice]` subsystem.

**Example:** `stt_min_record_seconds = 0.8`

### `stt_sample_rate`

- **Type:** integer
- **Shipped value:** `16000`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures stt sample rate for the `[voice]` subsystem.

**Example:** `stt_sample_rate = 16000`

### `stt_input_device`

- **Type:** string
- **Shipped value:** `default`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures stt input device for the `[voice]` subsystem.

**Example:** `stt_input_device = default`

### `vad_engine`

- **Type:** string
- **Shipped value:** `energy`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `energy`, `silero`
- **Status:** active

Selects energy-based or Silero voice activity detection.

**Example:** `vad_engine = energy`

### `vad_sample_rate`

- **Type:** integer
- **Shipped value:** `16000`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures vad sample rate for the `[voice]` subsystem.

**Example:** `vad_sample_rate = 16000`

### `vad_chunk_ms`

- **Type:** integer
- **Shipped value:** `30`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures vad chunk ms for the `[voice]` subsystem.

**Example:** `vad_chunk_ms = 30`

### `vad_speech_start_threshold`

- **Type:** number
- **Shipped value:** `0.38`
- **Runtime fallback:** `0.55` for the Silero path
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures vad speech start threshold for the `[voice]` subsystem.

**Example:** `vad_speech_start_threshold = 0.38`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `vad_speech_end_threshold`

- **Type:** number
- **Shipped value:** `0.28`
- **Runtime fallback:** `0.35` for the Silero path
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures vad speech end threshold for the `[voice]` subsystem.

**Example:** `vad_speech_end_threshold = 0.28`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `vad_min_speech_ms`

- **Type:** integer
- **Shipped value:** `180`
- **Runtime fallback:** `250` for the Silero path
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures vad min speech ms for the `[voice]` subsystem.

**Example:** `vad_min_speech_ms = 180`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `vad_min_silence_ms`

- **Type:** integer
- **Shipped value:** `1400`
- **Runtime fallback:** `900` for the Silero path
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures vad min silence ms for the `[voice]` subsystem.

**Example:** `vad_min_silence_ms = 1400`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `vad_pre_speech_padding_ms`

- **Type:** integer
- **Shipped value:** `1200`
- **Runtime fallback:** `900` for the Silero path
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures vad pre speech padding ms for the `[voice]` subsystem.

**Example:** `vad_pre_speech_padding_ms = 1200`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `vad_initial_timeout_seconds`

- **Type:** integer
- **Shipped value:** `12`
- **Runtime fallback:** `10` for the Silero path
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures vad initial timeout seconds for the `[voice]` subsystem.

**Example:** `vad_initial_timeout_seconds = 12`

**Notes:** The runtime fallback differs from the shipped value; the configured value remains authoritative when present.

### `session_exit_phrases`

- **Type:** comma-separated string list
- **Shipped value:** `exit,quit,stop listening,goodbye`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Comma-separated phrases that terminate a local voice session.

**Example:** `session_exit_phrases = exit,quit,stop listening,goodbye`
