-- __author__: clive
-- __date__: 2026-05-25
-- __description__: metadata JSON validity check for TTS voices


alter table orac_core.tts_voices
  add constraint tts_voice_ck3
  check (metadata_json is json)
;
