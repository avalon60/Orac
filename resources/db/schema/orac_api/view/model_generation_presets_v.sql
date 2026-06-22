--liquibase formatted sql

--changeset clive:model_generation_presets_v_create stripComments:false runOnChange:true context:core labels:core

create or replace force view orac_api.model_generation_presets_v as
   select
        model_preset_id
         , model_preset_code
         , model_preset_name
         , description
         , temperature
         , top_p
         , top_k
         , repeat_penalty
         , num_predict
         , seed
         , is_system_preset
         , is_active
         , created_by
         , created_on
         , updated_by
         , updated_on
         , row_version
       from orac_core.model_generation_presets;
--rollback drop view orac_api.model_generation_presets_v;
