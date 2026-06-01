--liquibase formatted sql

--changeset clive:plugin_invocations_v_create stripComments:false runOnChange:true

create or replace force view orac_api.plugin_invocations_v as
   select
        plugin_invocation_id
      , request_id
      , correlation_id
      , turn_id
      , conversation_id
      , message_id
      , user_id
      , plugin_id
      , plugin_name
      , action_type
      , capabilities
      , entitlements
      , policy_decision
      , policy_reason
      , confirmation_id
      , confirmation_status
      , execution_status
      , timeout_seconds
      , failure_type
      , failure_message
      , provenance_json
      , created_on
      , created_by
      , updated_on
      , updated_by
      , row_version
     from orac_core.plugin_invocations;
--rollback drop view orac_api.plugin_invocations_v;
