--liquibase formatted sql
--changeset clive:create_view_orac_api_conversation_memory_requests_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.conversation_memory_requests_v as
select memory_request_id,
       conversation_id,
       first_turn_index,
       last_turn_index,
       materialisation_profile,
       prompt_version,
       status_code,
       attempt_count,
       max_attempts,
       next_attempt_on,
       last_error_code,
       last_error_message,
       checkpoint_id,
       created_on,
       created_by,
       updated_on,
       updated_by,
       row_version
  from orac_core.conversation_memory_requests;
--rollback drop view orac_api.conversation_memory_requests_v;
