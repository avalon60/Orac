--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Maintains audit metadata for llm_input_representations.

--changeset clive:create_trigger_orac_core_llm_inrep_bu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.llm_inrep_bu
before update on orac_core.llm_input_representations
for each row
begin
  :new.created_on := :old.created_on;
  :new.created_by := :old.created_by;
  :new.updated_on := systimestamp;
  :new.updated_by := coalesce(
    sys_context('apex$session', 'app_user'),
    sys_context('userenv', 'proxy_user'),
    sys_context('userenv', 'session_user'),
    user
  );
  :new.row_version := nvl(:old.row_version, 0) + 1;
end;
/
--rollback drop trigger orac_core.llm_inrep_bu;

