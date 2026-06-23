--liquibase formatted sql

--changeset clive:create_index_orac_core_index_tts_voice_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'TTS_VOICE_UK1_IDX';
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

--rollback drop index orac_core.tts_voice_uk1_idx;
