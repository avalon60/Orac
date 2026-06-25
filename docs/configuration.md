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

### `connection_name`

- **Type:** string
- **Shipped value:** `orac-service`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** Yes for the corresponding database path
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Names the encrypted least-privilege core runtime database connection.

**Example:** `connection_name = orac-service`

### `plugin_connection_name`

- **Type:** string
- **Shipped value:** `orac-plugin`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** Yes for the corresponding database path
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Names the encrypted plugin-bridge database connection.

**Example:** `plugin_connection_name = orac-plugin`

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

Conversation history, prompt policy, rollover, and context-budget behavior.

### `enable_context_history`

- **Type:** boolean
- **Shipped value:** `true`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Enables persisted conversation history during context assembly.

**Example:** `enable_context_history = true`

### `keep_messages`

- **Type:** integer
- **Shipped value:** `200`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures keep messages for the `[context]` subsystem.

**Example:** `keep_messages = 200`

### `prune_every_n_turns`

- **Type:** integer
- **Shipped value:** `50`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** Any value valid for the described subsystem
- **Status:** active

Configures prune every n turns for the `[context]` subsystem.

**Example:** `prune_every_n_turns = 50`

### `enable_prompt_dump`

- **Type:** boolean
- **Shipped value:** `false`
- **Runtime fallback:** The shipped value is authoritative; loaders without a separate default require the configured key
- **Required:** No; supplied by the shipped configuration
- **Allowed values:** `true`, `false`
- **Status:** active

Writes assembled prompts to debug logs; enable only for local diagnostics.

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
