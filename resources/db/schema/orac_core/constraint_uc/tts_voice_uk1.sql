-- __author__: clive
-- __date__: 2026-05-25
-- __description__: provider-native uniqueness constraint for TTS voices


alter table orac_core.tts_voices
  add constraint tts_voice_uk1
  unique (provider_code, provider_voice_id)
;
