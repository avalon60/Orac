-- __author__: clive
-- __date__: 2026-05-25
-- __description__: primary key constraint for TTS voices runtime catalogue


alter table orac_core.tts_voices
  add constraint tts_voice_pk
  primary key (tts_voice_key)
;
