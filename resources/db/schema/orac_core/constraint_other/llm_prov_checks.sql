--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Enforces provider catalogue codes, periods, domains, and JSON boundary.

--changeset clive:create_constraints_orac_core_llm_prov_checks context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_PROV_CK1';
alter table orac_core.llm_providers add (
  constraint llm_prov_ck1 check (regexp_like(provider_code, '^[a-z][a-z0-9_]{0,99}$')),
  constraint llm_prov_ck2 check (processing_locality_domain_code = 'PROCESSING_LOCALITY'),
  constraint llm_prov_ck3 check (metadata_status_domain_code = 'PROVIDER_METADATA_STATUS'),
  constraint llm_prov_ck4 check (effective_to is null or effective_to > effective_from),
  constraint llm_prov_ck5 check (
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
--rollback alter table orac_core.llm_providers drop constraint llm_prov_ck5; alter table orac_core.llm_providers drop constraint llm_prov_ck4; alter table orac_core.llm_providers drop constraint llm_prov_ck3; alter table orac_core.llm_providers drop constraint llm_prov_ck2; alter table orac_core.llm_providers drop constraint llm_prov_ck1;
