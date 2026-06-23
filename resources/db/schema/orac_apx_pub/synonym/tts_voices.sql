--liquibase formatted sql

--changeset clive:create_synonym_orac_apx_pub_synonym_tts_voices context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: public-facing synonym for TTS voices runtime catalogue

create or replace synonym orac_apx_pub.tts_voices for orac_api.tts_voices_v;

--rollback drop synonym orac_apx_pub.tts_voices;
