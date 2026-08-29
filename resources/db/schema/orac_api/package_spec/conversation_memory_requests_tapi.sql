--liquibase formatted sql
--changeset clive:create_package_spec_orac_api_conversation_memory_requests_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_api.conversation_memory_requests_tapi
authid definer
as
  procedure ins(p_row in out orac_api.conversation_memory_requests_v%rowtype);
  procedure upd(p_row in out orac_api.conversation_memory_requests_v%rowtype);
end conversation_memory_requests_tapi;
/
--rollback drop package orac_api.conversation_memory_requests_tapi;
