--liquibase formatted sql

--changeset clive:users_v_create stripComments:false runOnChange:true

create or replace force view orac_api.users_v as
   select
        user_id
         , username
         , display_name
         , email
         , is_active
         , created_on
         , created_by
         , updated_on
         , updated_by
         , row_version
       from orac.users;
--rollback drop view orac_api.users_v;
