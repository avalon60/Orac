# Runtime User Preferences

Runtime user preferences are values that Orac resolves for a request before it
builds conversational context, generation options, or local text-to-speech
metadata. They are applied by `Orac._apply_user_preference_meta()`.

This page documents the implemented runtime contract. It does not describe
future preference ideas, hidden UI metadata, or removed catalogue rows as active
features.

## Precedence

Scalar runtime preferences use this precedence, in order:

`explicit request metadata > saved user preference > *_default orac.ini setting > safe built-in default`

Invalid explicit, saved, or configured values are ignored with a warning, then
Orac falls through to the next source. Numeric preferences are clamped to their
supported range after parsing.

`tts_voice` follows a voice-catalogue path because it resolves to provider
metadata, not just a scalar value:

`request tts_voice/tts_voice_key > saved tts_voice preference > configured engine voice > discovered default voice > unavailable marker`

## Runtime Preferences

| Preference | Effect | Type and acceptable values | Defaults and validation | Implemented use |
|---|---|---|---|---|
| `timezone` | Conversational engine, UI/display | String; valid IANA timezone name such as `Europe/London`. | Config default `settings.timezone_default`; built-in `Europe/London`. Invalid values are ignored with warning/fallback. | Builds clock/date context, local time instructions, and timezone-derived location fallback. |
| `date_format` | Conversational engine, UI/display | String; `DD-MON-YYYY HH24:MI`, `YYYY-MM-DD HH24:MI`, `DD/MM/YYYY HH24:MI`, or `DD Mon YYYY HH24:MI`. | Config default `settings.date_format_default`; built-in `DD-MON-YYYY HH24:MI`. Unsupported masks are ignored with warning/fallback. | Formats user-facing clock/date context. |
| `force_concise` | Conversational engine | Boolean. | Config default `settings.force_concise_default`; built-in `false`. | Adds `Keep answers concise.` to contextual prompt only when true. |
| `max_tokens` | Conversational engine | Integer. | Config default `settings.max_tokens_default`; bounded to `1..32768`; optionally capped by `settings.max_tokens_limit` when that setting is present and at least `1`. | Applied to provider-neutral generation options as `num_predict`; the connector keeps `num_predict` for Ollama and maps it to `max_tokens` for LM Studio/OpenAI-compatible providers. |
| `show_reasoning` | Conversational engine metadata | Boolean. | Config default `settings.show_reasoning_default`; built-in `false`. | Resolved into request/assistant metadata and diagnostic logging. Current connector paths still force visible model reasoning off where the code does so, so this is not a guarantee that reasoning text will be shown. |
| `strip_reasoning_tags` | Conversational engine, UI/display | Boolean. | Config default `settings.strip_reasoning_tags_default`; built-in `true`. | Controls non-streaming `_strip_reasoning_tags` and streaming `ReasoningTagStreamFilter` output cleanup. |
| `tts_voice` | Voice/TTS | String voice key such as `kokoro:bm_george` or `piper:en_GB-alba-medium`; request metadata may also carry an already-resolved runtime voice dict. | Saved preference is resolved through the TTS catalogue. Config fallback uses `voice.tts_kokoro_voice` when `voice.tts_engine = kokoro`, otherwise `voice.tts_voice` for Piper. | Selects provider-specific TTS engine and voice from catalogue metadata. |
| `tts_rate` | Voice/TTS | Number. | Config default `settings.tts_rate_default`; bounded to `0.25..4.0`. | Added to `tts_options` as an engine-neutral speaking-rate hint. TTS adapters map it to supported engine options or safely ignore it. |
| `tts_pitch` | Voice/TTS | Number. | Config default `settings.tts_pitch_default`; bounded to `-10.0..10.0`. | Added to `tts_options` as an engine-neutral pitch hint. TTS adapters map it to supported engine options or safely ignore it. |

## Preference UI Metadata

User preference definitions may include UI metadata such as `control_type`,
`min_number`, `max_number`, `step_number`, `unit_label`,
`display_min_label`, `display_max_label`, and `display_value_format`.
`control_type = 'slider'` is UI sugar for bounded numeric preferences.

APEX Page 6 uses this metadata only to render the editing control. Slider
preferences are rendered as native range inputs created inside the fixed
`ORAC_PREF_SLIDER_HOST` host; the submitted APEX slider item is hidden and
contains only the selected value. Submitted values still pass through
`orac_code.user_preferences_api`, which reloads the authoritative metadata from
`preference_definitions_v` and validates the value server-side.
Client-submitted Page 6 metadata such as `P6_MIN_NUMBER`, `P6_MAX_NUMBER`, or
`P6_STEP_NUMBER` must not be trusted for validation.

## TTS Portability

`tts_voice`, `tts_rate`, and `tts_pitch` are portable hints. They are not a
promise that every TTS engine exposes the same controls. Each implemented
adapter must map the hint to an engine-specific option, clamp it through the
runtime preference validator, or ignore it safely.

| Engine | `tts_voice` | `tts_rate` | `tts_pitch` |
|---|---|---|---|
| Kokoro | Maps to Kokoro `voice` selection. | Mapped to OpenAI-compatible speech `speed`. | Unsupported; debug-logged and ignored, and not sent as `pitch`. |
| Piper | Maps to Piper voice/model path selection. | Unsupported; debug-logged and ignored. | Unsupported; debug-logged and ignored. |

Only Kokoro and Piper are currently implemented local TTS engines. Generic
provider fields in the voice catalogue are extension points, not evidence that
another provider is available. Unsupported provider codes are not treated as
working engines.

## Hidden, UI-Only, and Removed Preferences

`landing_page_id` and `enable_advanced_mode` are hidden/non-editable UI
preferences. They must not be presented as implemented conversational runtime
behaviour.

`email_opt_in` has been removed from active catalogue/build references and must
not be documented as an active runtime preference.
