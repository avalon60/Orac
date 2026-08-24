--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Restricts provider transport evidence, adapter states, periods, and JSON.

--changeset clive:create_constraints_orac_core_llm_prvin_checks context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_PRVIN_CK1';
alter table orac_core.llm_provider_inputs add (
  constraint llm_prvin_ck1 check (evidence_state_domain_code = 'CAPABILITY_EVIDENCE_STATE'),
  constraint llm_prvin_ck2 check (evidence_state_ref_value_code in ('API_DECLARED', 'REJECTED')),
  constraint llm_prvin_ck3 check (adapter_status_domain_code = 'ADAPTER_SUPPORT_STATUS'),
  constraint llm_prvin_ck4 check (effective_to is null or effective_to > effective_from),
  constraint llm_prvin_ck5 check (
       (evidence_state_ref_value_code = 'REJECTED' and rejection_reason is not null)
    or (evidence_state_ref_value_code = 'API_DECLARED' and rejection_reason is null)
  ),
  constraint llm_prvin_ck6 check (
    native_properties is null or (
      lengthb(json_serialize(native_properties returning varchar2(32767))) <= 8192
      and json_equal(
        json_transform(
          native_properties,
          remove '$.schema_version',
          remove '$.request_fields',
          remove '$.encoding_shape',
          remove '$.sdk_options',
          remove '$.native_labels',
          remove '$.response_metadata',
          remove '$.runtime_hints',
          remove '$.adapter_quirks'
        ),
        json('{}')
      )
      and not json_exists(native_properties, '$..password')
      and not json_exists(native_properties, '$..secret')
      and not json_exists(native_properties, '$..token')
      and not json_exists(native_properties, '$..api_key')
      and not json_exists(native_properties, '$..credential')
      and not json_exists(native_properties, '$..prompt')
      and not json_exists(native_properties, '$..content')
      and not json_exists(native_properties, '$..filename')
      and not json_exists(native_properties, '$..path')
      and not json_exists(native_properties, '$..managed_key')
      and not json_exists(native_properties, '$..capability')
      and not json_exists(native_properties, '$..capabilities')
      and not json_exists(native_properties, '$..evidence_state')
      and not json_exists(native_properties, '$..locality')
      and not json_exists(native_properties, '$..model_revision')
      and not json_exists(native_properties, '$..mime_policy')
      and not json_exists(native_properties, '$..enabled')
      and not json_exists(native_properties, '$..health')
      and not json_exists(native_properties, '$..limits')
      and not json_exists(native_properties, '$..max_value')
    )
  )
);
--rollback alter table orac_core.llm_provider_inputs drop constraint llm_prvin_ck6; alter table orac_core.llm_provider_inputs drop constraint llm_prvin_ck5; alter table orac_core.llm_provider_inputs drop constraint llm_prvin_ck4; alter table orac_core.llm_provider_inputs drop constraint llm_prvin_ck3; alter table orac_core.llm_provider_inputs drop constraint llm_prvin_ck2; alter table orac_core.llm_provider_inputs drop constraint llm_prvin_ck1;
