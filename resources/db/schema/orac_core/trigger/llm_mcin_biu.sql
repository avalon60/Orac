--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Restricts model input rows to current positive behavioural evidence.

--changeset clive:create_trigger_orac_core_llm_mcin_biu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.llm_mcin_biu
before insert or update on orac_core.llm_model_cap_inputs
for each row
declare
  l_positive_parent_count pls_integer;
begin
  select count(*)
    into l_positive_parent_count
    from orac_core.llm_model_capabilities
   where model_capability_id = :new.model_capability_id
     and evidence_state_ref_value_code in (
       'MODEL_METADATA_VERIFIED',
       'BOUNDED_PROBE_VERIFIED'
     )
     and effective_from <= systimestamp
     and (effective_to is null or effective_to > systimestamp);

  if l_positive_parent_count <> 1
  then
    raise_application_error(
      -20643,
      'Model input associations require current positive behavioural evidence.'
    );
  end if;

  if updating
  then
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
  end if;
end;
/
--rollback drop trigger orac_core.llm_mcin_biu;

