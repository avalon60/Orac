--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Enforces exact model identity, evidence maturity, and audit rules.

--changeset clive:create_trigger_orac_core_llm_modcap_biu context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace trigger orac_core.llm_modcap_biu
before insert or update on orac_core.llm_model_capabilities
for each row
declare
  l_registry_match_count pls_integer;
begin
  select count(*)
    into l_registry_match_count
    from orac_core.llm_registry
   where llm_id = :new.llm_id
     and provider = :new.provider_code
     and model = :new.model_identity;

  if l_registry_match_count <> 1
  then
    raise_application_error(
      -20640,
      'Model evidence must match the exact registered provider/model identity.'
    );
  end if;

  if updating
  then
    if :old.evidence_state_ref_value_code = 'BOUNDED_PROBE_VERIFIED'
       and :new.evidence_state_ref_value_code = 'MODEL_METADATA_VERIFIED'
    then
      raise_application_error(-20641, 'Model evidence maturity cannot be downgraded.');
    end if;

    if :old.evidence_state_ref_value_code = 'REJECTED'
       and :new.evidence_state_ref_value_code in (
         'MODEL_METADATA_VERIFIED',
         'BOUNDED_PROBE_VERIFIED'
       )
       and (
         :new.checked_on <= :old.checked_on
         or :new.reviewed_by is null
         or :new.source_reference = :old.source_reference
       )
    then
      raise_application_error(
        -20642,
        'Replacing rejected evidence requires a later review and new evidence.'
      );
    end if;

    if :new.evidence_state_ref_value_code = 'REJECTED'
       and :old.evidence_state_ref_value_code <> 'REJECTED'
    then
      update orac_core.llm_model_cap_inputs
         set effective_to = coalesce(effective_to, systimestamp)
       where model_capability_id = :old.model_capability_id
         and effective_to is null;
    end if;

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
--rollback drop trigger orac_core.llm_modcap_biu;

