-- __author__: clive
-- __date__: 2026-05-25
-- __description__: default flag check for TTS voices


alter table orac_core.tts_voices
  add constraint tts_voice_ck1
  check (default_yn in ('N', 'Y'))
;
