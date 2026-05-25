--liquibase formatted sql

--changeset clive:plugin_audit_events_v_create stripComments:false runOnChange:true

create or replace force view orac_api.plugin_audit_events_v as
   select
        plugin_audit_event_id
      , plugin_invocation_id
      , event_type
      , event_status
      , event_message
      , policy_decision
      , confirmation_id
      , execution_status
      , failure_type
      , failure_message
      , event_payload_json
      , created_on
      , created_by
      , updated_on
      , updated_by
      , row_version
     from orac_core.plugin_audit_events;
--rollback drop view orac_api.plugin_audit_events_v;
