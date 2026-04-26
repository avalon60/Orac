--liquibase formatted sql

--changeset clive:user_synonyms_v_create stripComments:false runOnChange:true

create or replace force view orac_api.user_synonyms_v as
   select
        user_id
         , alias_type
         , alias_value
         , is_active
         , created_on
         , created_by
         , updated_on
         , updated_by
         , row_version
       from orac.user_synonyms;
--rollback drop view orac_api.user_synonyms_v;
