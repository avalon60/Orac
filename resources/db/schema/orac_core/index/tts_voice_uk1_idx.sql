-- __author__: clive
-- __date__: 2026-05-25
-- __description__: provider-native uniqueness index for TTS voices


create unique index orac_core.tts_voice_uk1_idx
  on orac_core.tts_voices
  (
    provider_code asc,
    provider_voice_id asc
  )
;
