-- __author__: clive
-- __date__: 2026-05-25
-- __description__: primary key index for TTS voices runtime catalogue


create unique index orac_core.tts_voice_pk
  on orac_core.tts_voices
  (
    tts_voice_key asc
  )
;
