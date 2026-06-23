--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_tts_voice_ck2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'TTS_VOICE_CK2';
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: enabled flag check for TTS voices


alter table orac_core.tts_voices
  add constraint tts_voice_ck2
  check (enabled_yn in ('N', 'Y'))
;

--rollback alter table orac_core.tts_voices drop constraint tts_voice_ck2;
