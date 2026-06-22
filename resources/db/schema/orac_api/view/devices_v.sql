--liquibase formatted sql

--changeset clive:devices_v_create stripComments:false runOnChange:true context:core labels:core

create or replace force view orac_api.devices_v as
   select
        device_id
         , user_id
         , host_name
         , is_active
         , created_on
         , created_by
         , updated_on
         , updated_by
         , row_version
       from orac_core.devices;
--rollback drop view orac_api.devices_v;
