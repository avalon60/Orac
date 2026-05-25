-- __author__: clive
-- __date__: 2026-05-25
-- __description__: enabled flag check for TTS voices


alter table orac_core.tts_voices
  add constraint tts_voice_ck2
  check (enabled_yn in ('N', 'Y'))
;
