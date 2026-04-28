--liquibase formatted sql

--changeset clive:orac_personalities_v_create stripComments:false runOnChange:true

create or replace force view orac_api.orac_personalities_v as
   select
        personality_id
         , personality_code
         , personality_name
         , description
         , attitude_base_level
         , sarcasm_level
         , verbosity_level
         , allow_humour
         , allow_critique
         , enforce_precision
         , admit_uncertainty
         , packaged_persona
         , system_prompt
         , style_prompt
         , is_active
         , created_on
         , created_by
         , updated_on
         , updated_by
         , row_version
       from orac_core.orac_personalities;
--rollback drop view orac_api.orac_personalities_v;
