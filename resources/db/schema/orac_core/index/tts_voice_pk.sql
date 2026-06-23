--liquibase formatted sql

--changeset clive:create_index_orac_core_index_tts_voice_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'TTS_VOICE_PK';
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: primary key index for TTS voices runtime catalogue


create unique index orac_core.tts_voice_pk
  on orac_core.tts_voices
  (
    tts_voice_key asc
  )
;

--rollback drop index orac_core.tts_voice_pk;
