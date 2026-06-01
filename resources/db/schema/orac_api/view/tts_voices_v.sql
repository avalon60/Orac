--liquibase formatted sql

--changeset clive:tts_voices_v_create stripComments:false runOnChange:true

create or replace force view orac_api.tts_voices_v as
   select
        tts_voice_key
      , provider_code
      , provider_voice_id
      , display_name
      , language_code
      , locale_code
      , voice_quality
      , model_path
      , config_path
      , metadata_json
      , default_yn
      , enabled_yn
      , sort_order
      , loaded_on
     from orac_core.tts_voices;
--rollback drop view orac_api.tts_voices_v;
