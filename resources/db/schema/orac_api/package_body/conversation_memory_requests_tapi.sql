--liquibase formatted sql
--changeset clive:create_package_body_orac_api_conversation_memory_requests_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_api.conversation_memory_requests_tapi
as
  procedure ins(p_row in out orac_api.conversation_memory_requests_v%rowtype)
  is
  begin
    insert into orac_api.conversation_memory_requests_v
    (
      conversation_id, first_turn_index, last_turn_index,
      materialisation_profile, prompt_version, status_code,
      attempt_count, max_attempts, next_attempt_on
    )
    values
    (
      p_row.conversation_id, p_row.first_turn_index, p_row.last_turn_index,
      p_row.materialisation_profile, p_row.prompt_version, p_row.status_code,
      p_row.attempt_count, p_row.max_attempts, p_row.next_attempt_on
    )
    returning memory_request_id, row_version
      into p_row.memory_request_id, p_row.row_version;
  end ins;

  procedure upd(p_row in out orac_api.conversation_memory_requests_v%rowtype)
  is
  begin
    update orac_api.conversation_memory_requests_v
       set status_code        = p_row.status_code,
           attempt_count      = p_row.attempt_count,
           next_attempt_on    = p_row.next_attempt_on,
           last_error_code    = p_row.last_error_code,
           last_error_message = p_row.last_error_message,
           checkpoint_id      = p_row.checkpoint_id
     where memory_request_id = p_row.memory_request_id
       and row_version = p_row.row_version
    returning row_version into p_row.row_version;
    if sql%rowcount = 0
    then
      raise_application_error(-20072, 'Conversation memory request was modified concurrently.');
    end if;
  end upd;
end conversation_memory_requests_tapi;
/
--rollback drop package body orac_api.conversation_memory_requests_tapi;
