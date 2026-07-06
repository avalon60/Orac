--liquibase formatted sql

--changeset clive:plugin_services_v_create stripComments:false runOnChange:true context:core labels:core

create or replace force view orac_api.plugin_services_v as
   select
        plugin_service_id
      , plugin_id
      , service_code
      , service_name
      , entry_point
      , execution_model
      , manifest_policy
      , policy_override
      , current_state
      , owner_id
      , lease_token
      , lease_expires_on
      , last_started_on
      , last_heartbeat_on
      , last_tick_on
      , last_error_message
      , created_on
      , created_by
      , updated_on
      , updated_by
      , row_version
     from orac_core.plugin_services;
--rollback drop view orac_api.plugin_services_v;
