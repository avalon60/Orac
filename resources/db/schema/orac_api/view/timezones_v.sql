--liquibase formatted sql

--changeset clive:timezones_v_create stripComments:false runOnChange:true context:core labels:core

create or replace force view orac_api.timezones_v as
   select
        timezone_id
      , tz_name
      , display_label
      , region_group
      , display_sequence
      , is_active
      , created_on
      , created_by
      , updated_on
      , updated_by
      , row_version
     from orac_core.timezones;
--rollback drop view orac_api.timezones_v;
