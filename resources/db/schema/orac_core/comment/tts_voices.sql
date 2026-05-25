comment on table orac_core.tts_voices is
  'Startup-refreshed runtime catalogue of available selectable text-to-speech voices.'
;

comment on column orac_core.tts_voices.tts_voice_key is
  'Stable soft-reference key, normally provider_code || '':'' || provider_voice_id.'
;

comment on column orac_core.tts_voices.provider_code is
  'TTS provider code such as piper, kokoro, or indextts.'
;

comment on column orac_core.tts_voices.provider_voice_id is
  'Provider-native voice identifier.'
;

comment on column orac_core.tts_voices.display_name is
  'Human-friendly display name for preference LOVs.'
;

comment on column orac_core.tts_voices.language_code is
  'Optional language code derived from provider metadata.'
;

comment on column orac_core.tts_voices.locale_code is
  'Optional locale code derived from provider metadata.'
;

comment on column orac_core.tts_voices.voice_quality is
  'Optional voice quality or tier reported by the provider.'
;

comment on column orac_core.tts_voices.model_path is
  'Optional local model path for filesystem-backed TTS providers.'
;

comment on column orac_core.tts_voices.config_path is
  'Optional local model configuration path for filesystem-backed TTS providers.'
;

comment on column orac_core.tts_voices.metadata_json is
  'Provider-specific metadata stored as JSON text.'
;

comment on column orac_core.tts_voices.default_yn is
  'Y when this row matches the configured runtime default voice.'
;

comment on column orac_core.tts_voices.enabled_yn is
  'Y when the discovered voice is usable for runtime selection.'
;

comment on column orac_core.tts_voices.sort_order is
  'Optional display ordering within a provider.'
;

comment on column orac_core.tts_voices.loaded_on is
  'Timestamp when the row was loaded into the runtime catalogue.'
;
