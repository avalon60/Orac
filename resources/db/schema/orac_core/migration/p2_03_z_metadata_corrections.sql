--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Applies append-only P2-03 seed corrections and rollback policy.

--changeset clive:p2_03_deactivate_non_contract_locality context:core labels:core stripComments:false
update orac_core.domain_ref_values
   set active_yn = 'N'
 where domain_code = 'PROCESSING_LOCALITY'
   and ref_value_code = 'UNMAPPED';
--rollback select 1 from dual;

--changeset clive:p2_03_protected_domain_rollback_policy context:core labels:core stripComments:false
select 1 from dual;
--rollback update orac_core.domain_ref_values set active_yn = 'N' where domain_code in ('CAPABILITY_CLASS', 'CAPABILITY_EVIDENCE_STATE', 'CAPABILITY_LIFECYCLE', 'PROVIDER_METADATA_STATUS', 'PROCESSING_LOCALITY', 'ADAPTER_SUPPORT_STATUS', 'MIME_MATCH_KIND', 'LIMIT_DIMENSION', 'LIMIT_UNIT', 'BOUND_OPERATOR');
--rollback update orac_core.domain_codes set active_yn = 'N' where domain_code in ('CAPABILITY_CLASS', 'CAPABILITY_EVIDENCE_STATE', 'CAPABILITY_LIFECYCLE', 'PROVIDER_METADATA_STATUS', 'PROCESSING_LOCALITY', 'ADAPTER_SUPPORT_STATUS', 'MIME_MATCH_KIND', 'LIMIT_DIMENSION', 'LIMIT_UNIT', 'BOUND_OPERATOR');
