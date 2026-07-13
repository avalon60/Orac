--liquibase formatted sql

--changeset clive:create_view_orac_api_knowledge_ingestion_requests_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_ingestion_requests_v as
select ingestion_request_id,
       source_object_id,
       document_id,
       document_version_id,
       processing_profile_code,
       processing_instruction,
       status_code,
       stage_code,
       attempts,
       max_attempts,
       next_attempt_on,
       lease_owner,
       lease_token,
       lease_expires_on,
       last_error_code,
       last_error_message,
       completed_on,
       created_by,
       created_on,
       updated_by,
       updated_on,
       row_version
  from orac_core.knowledge_ingestion_requests;
--rollback drop view orac_api.knowledge_ingestion_requests_v;
