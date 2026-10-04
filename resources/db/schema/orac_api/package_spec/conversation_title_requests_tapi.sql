--liquibase formatted sql
--changeset clive:create_package_spec_orac_api_conversation_title_requests_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_api.conversation_title_requests_tapi authid definer as
  procedure ins(p_row in out nocopy orac_api.conversation_title_requests_v%rowtype);
  procedure upd(p_title_request_id in number, p_row in orac_api.conversation_title_requests_v%rowtype);
  function enqueue_request(p_conversation_id in number) return number;
  function try_claim_next_request(p_owner_id in varchar2, p_lease_seconds in number) return number;
  procedure complete_request(p_request_id in number, p_owner_id in varchar2, p_lease_token in varchar2, p_title in varchar2);
  procedure fail_request(p_request_id in number, p_owner_id in varchar2, p_lease_token in varchar2, p_error_message in varchar2, p_retryable_yn in varchar2);
end conversation_title_requests_tapi;
/
--rollback drop package orac_api.conversation_title_requests_tapi;
