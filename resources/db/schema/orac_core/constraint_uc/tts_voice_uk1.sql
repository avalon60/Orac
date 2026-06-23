--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_uc_tts_voice_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'TTS_VOICE_UK1';
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: provider-native uniqueness constraint for TTS voices


alter table orac_core.tts_voices
  add constraint tts_voice_uk1
  unique (provider_code, provider_voice_id)
;

--rollback alter table orac_core.tts_voices drop constraint tts_voice_uk1;
