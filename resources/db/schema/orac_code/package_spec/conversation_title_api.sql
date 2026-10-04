--liquibase formatted sql
--changeset clive:create_package_spec_orac_code_conversation_title_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_code.conversation_title_api authid definer as
  function enqueue_request(p_conversation_id in number) return number;
  function try_claim_next_request(p_owner_id in varchar2, p_lease_seconds in number default 180) return number;
  procedure complete_request(p_request_id in number, p_owner_id in varchar2, p_lease_token in varchar2, p_title in varchar2);
  procedure fail_request(p_request_id in number, p_owner_id in varchar2, p_lease_token in varchar2, p_error_message in varchar2, p_retryable_yn in varchar2 default 'Y');
end conversation_title_api;
/
--rollback drop package orac_code.conversation_title_api;
