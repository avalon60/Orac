--liquibase formatted sql

--changeset clive:p2_03_llm_compatibility_recompile context:core labels:core stripComments:false runAlways:true
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:4 select count(*) from all_objects where (owner = 'ORAC_API' and object_name = 'LLM_REGISTRY_TAPI' and object_type in ('PACKAGE', 'PACKAGE BODY')) or (owner = 'ORAC_CODE' and object_name in ('LLM_REGISTRY_PROBE_V', 'LLM_USAGE_BREAKDOWN_V') and object_type = 'VIEW');
alter package orac_api.llm_registry_tapi compile specification;
alter package orac_api.llm_registry_tapi compile body;
alter view orac_code.llm_registry_probe_v compile;
alter view orac_code.llm_usage_breakdown_v compile;

--rollback select 1 from dual;
