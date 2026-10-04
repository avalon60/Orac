--liquibase formatted sql
--changeset clive:create_view_orac_api_conversation_title_requests_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.conversation_title_requests_v as
select title_request_id, conversation_id, status_code, attempts, max_attempts,
       next_attempt_on, lease_owner, lease_token, lease_expires_on,
       last_error_message, completed_on, created_on, created_by, updated_on,
       updated_by, row_version
  from orac_core.conversation_title_requests;
--rollback drop view orac_api.conversation_title_requests_v;
