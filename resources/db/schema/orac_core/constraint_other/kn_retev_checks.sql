--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Constrains safe knowledge retrieval audit event values.

--changeset clive:create_constraint_other_orac_core_kn_retev_checks context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name in ('KN_RETEV_UUID_CK', 'KN_RETEV_EVENT_CK', 'KN_RETEV_OPERATION_CK', 'KN_RETEV_TARGET_CK', 'KN_RETEV_STATUS_CK', 'KN_RETEV_NUMBERS_CK', 'KN_RETEV_HASH_CK', 'KN_RETEV_USER_TRIM_CK');
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_uuid_ck
  check (regexp_like(retrieval_id, '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'));
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_event_ck
  check (event_type_code in ('DECISION', 'OUTCOME'));
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_operation_ck
  check (operation_code in ('METADATA', 'CONTENT', 'CHUNK_SEARCH'));
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_target_ck
  check (target_type_code is null or target_type_code in ('DOCUMENT', 'DOCUMENT_VERSION', 'EXTRACTION', 'ARTEFACT', 'CHUNK_SET'));
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_status_ck
  check (status_code in ('APPROVED', 'REJECTED', 'COMPLETED', 'FAILED', 'CANCELLED'));
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_numbers_ck
  check (
    coalesce(expected_byte_size, 0) >= 0
    and coalesce(returned_byte_size, 0) >= 0
    and coalesce(member_count, 0) >= 0
    and coalesce(chunk_count, 0) >= 0
    and coalesce(duration_ms, 0) >= 0
  );
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_hash_ck
  check (returned_sha256 is null or regexp_like(returned_sha256, '^[0-9a-f]{64}$'));
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_user_trim_ck
  check (username_snapshot = trim(username_snapshot));
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_user_trim_ck;
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_hash_ck;
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_numbers_ck;
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_status_ck;
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_target_ck;
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_operation_ck;
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_event_ck;
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_uuid_ck;

--changeset clive:extend_constraint_other_orac_core_kn_retev_operation_p1_07 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_RETEV_OPERATION_CK' and constraint_type = 'C';
alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_operation_ck;
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_operation_ck
  check (operation_code in ('METADATA', 'CONTENT', 'CHUNK_SEARCH', 'MATERIALISATION_POLICY'));
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_operation_ck;
--rollback alter table orac_core.knowledge_retrieval_events add constraint kn_retev_operation_ck check (operation_code in ('METADATA', 'CONTENT', 'CHUNK_SEARCH'));

--changeset clive:extend_constraint_other_orac_core_kn_retev_operation_p1_08 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_RETEV_OPERATION_CK' and constraint_type = 'C';
alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_operation_ck;
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_operation_ck
  check (operation_code in ('METADATA', 'CONTENT', 'CHUNK_SEARCH', 'MATERIALISATION_POLICY', 'MODEL_SUBMISSION'));
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_operation_ck;
--rollback alter table orac_core.knowledge_retrieval_events add constraint kn_retev_operation_ck check (operation_code in ('METADATA', 'CONTENT', 'CHUNK_SEARCH', 'MATERIALISATION_POLICY'));

--changeset clive:extend_constraint_other_orac_core_kn_retev_governed_retrieval_p2a context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:2 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name in ('KN_RETEV_OPERATION_CK', 'KN_RETEV_TARGET_CK') and constraint_type = 'C';
alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_operation_ck;
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_operation_ck
  check (operation_code in ('METADATA', 'CONTENT', 'CHUNK_SEARCH', 'MATERIALISATION_POLICY', 'MODEL_SUBMISSION', 'GOVERNED_RETRIEVAL'));
alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_target_ck;
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_target_ck
  check (target_type_code is null or target_type_code in ('DOCUMENT', 'DOCUMENT_VERSION', 'EXTRACTION', 'ARTEFACT', 'CHUNK_SET', 'RETRIEVAL_DOMAIN'));
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_target_ck;
--rollback alter table orac_core.knowledge_retrieval_events add constraint kn_retev_target_ck check (target_type_code is null or target_type_code in ('DOCUMENT', 'DOCUMENT_VERSION', 'EXTRACTION', 'ARTEFACT', 'CHUNK_SET'));
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_operation_ck;
--rollback alter table orac_core.knowledge_retrieval_events add constraint kn_retev_operation_ck check (operation_code in ('METADATA', 'CONTENT', 'CHUNK_SEARCH', 'MATERIALISATION_POLICY', 'MODEL_SUBMISSION'));

--changeset clive:extend_kn_retev_operation_authorised_project_search context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_RETEV_OPERATION_CK' and constraint_type = 'C';
alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_operation_ck;
alter table orac_core.knowledge_retrieval_events add constraint kn_retev_operation_ck
  check (operation_code in ('METADATA', 'CONTENT', 'CHUNK_SEARCH', 'MATERIALISATION_POLICY', 'MODEL_SUBMISSION', 'GOVERNED_RETRIEVAL', 'AUTHORISED_PROJECT_SEARCH'));
--rollback alter table orac_core.knowledge_retrieval_events drop constraint kn_retev_operation_ck;
--rollback alter table orac_core.knowledge_retrieval_events add constraint kn_retev_operation_ck check (operation_code in ('METADATA', 'CONTENT', 'CHUNK_SEARCH', 'MATERIALISATION_POLICY', 'MODEL_SUBMISSION', 'GOVERNED_RETRIEVAL'));
