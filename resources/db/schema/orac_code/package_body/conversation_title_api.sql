--liquibase formatted sql
--changeset clive:create_package_body_orac_code_conversation_title_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_code.conversation_title_api as
  function enqueue_request(p_conversation_id in number) return number is
  begin
    return orac_api.conversation_title_requests_tapi.enqueue_request(p_conversation_id);
  end enqueue_request;
  function try_claim_next_request(p_owner_id in varchar2, p_lease_seconds in number default 180) return number is
  begin
    return orac_api.conversation_title_requests_tapi.try_claim_next_request(p_owner_id, p_lease_seconds);
  end try_claim_next_request;
  procedure complete_request(p_request_id in number, p_owner_id in varchar2, p_lease_token in varchar2, p_title in varchar2) is
  begin
    orac_api.conversation_title_requests_tapi.complete_request(p_request_id, p_owner_id, p_lease_token, p_title);
  end complete_request;
  procedure fail_request(p_request_id in number, p_owner_id in varchar2, p_lease_token in varchar2, p_error_message in varchar2, p_retryable_yn in varchar2 default 'Y') is
  begin
    orac_api.conversation_title_requests_tapi.fail_request(p_request_id, p_owner_id, p_lease_token, p_error_message, p_retryable_yn);
  end fail_request;
end conversation_title_api;
/
--rollback drop package body orac_code.conversation_title_api;
