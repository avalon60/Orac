--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_tts_voices_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: compatibility synonym for TTS voices runtime catalogue view

create or replace synonym orac.tts_voices_v for orac_api.tts_voices_v;

--rollback drop synonym orac.tts_voices_v;
