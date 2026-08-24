--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Keeps controlled P2-03 metadata out of legacy registry JSON.

--changeset clive:create_constraint_orac_core_llm_reg_ck3_p203_reserved context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from orac_core.llm_registry where json_exists(properties, '$.model_type') or json_exists(properties, '$.locality') or json_exists(properties, '$.capability') or json_exists(properties, '$.capabilities') or json_exists(properties, '$.modality') or json_exists(properties, '$.modalities') or json_exists(properties, '$.mime') or json_exists(properties, '$.mime_types') or json_exists(properties, '$.evidence') or json_exists(properties, '$.evidence_state') or json_exists(properties, '$.limits') or json_exists(properties, '$.model_revision') or json_exists(properties, '$.model_digest');
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'LLM_REG_CK3';
alter table orac_core.llm_registry add constraint llm_reg_ck3 check (
     properties is null
  or (
       not json_exists(properties, '$.model_type')
   and not json_exists(properties, '$.locality')
   and not json_exists(properties, '$.capability')
   and not json_exists(properties, '$.capabilities')
   and not json_exists(properties, '$.modality')
   and not json_exists(properties, '$.modalities')
   and not json_exists(properties, '$.mime')
   and not json_exists(properties, '$.mime_types')
   and not json_exists(properties, '$.evidence')
   and not json_exists(properties, '$.evidence_state')
   and not json_exists(properties, '$.limits')
   and not json_exists(properties, '$.model_revision')
   and not json_exists(properties, '$.model_digest')
  )
);
--rollback alter table orac_core.llm_registry drop constraint llm_reg_ck3;
