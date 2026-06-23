--liquibase formatted sql

--changeset clive:user_preferences_v_create stripComments:false runOnChange:true context:core labels:core

create or replace force view orac_api.user_preferences_v as
   select
        pref_id
         , user_id
         , pref_key
         , pref_value
         , value_type
         , created_on
         , created_by
         , updated_on
         , updated_by
         , row_version
       from orac_core.user_preferences;
--rollback drop view orac_api.user_preferences_v;
