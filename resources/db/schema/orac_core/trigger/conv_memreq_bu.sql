--liquibase formatted sql
--changeset clive:create_trigger_orac_core_conv_memreq_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.conv_memreq_bu
before update on orac_core.conversation_memory_requests
for each row
begin
  :new.updated_on := systimestamp;
  :new.updated_by := coalesce(
                       sys_context('userenv', 'client_identifier'),
                       sys_context('userenv', 'proxy_user'),
                       sys_context('userenv', 'session_user'),
                       user
                     );
  :new.row_version := nvl(:old.row_version, 1) + 1;
end;
/
--rollback drop trigger orac_core.conv_memreq_bu;
