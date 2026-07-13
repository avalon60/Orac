--liquibase formatted sql

--changeset clive:create_view_orac_code_knowledge_ingestion_requests_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.knowledge_ingestion_requests_v as
select req.ingestion_request_id,
       req.status_code,
       case req.status_code
         when 'QUEUED' then 'Queued - awaiting Core acceptance'
         when 'PROCESSING' then 'Handed off - Core processing'
         when 'RETRY_WAIT' then 'Core ingestion retry waiting'
         when 'COMPLETED' then 'Completed'
         when 'FAILED' then 'Core ingestion failed'
         else req.status_code
       end status_label,
       req.stage_code,
       req.attempts,
       req.max_attempts,
       req.next_attempt_on,
       req.lease_owner,
       req.lease_token,
       req.lease_expires_on,
       req.last_error_code,
       req.last_error_message,
       req.completed_on,
       req.created_on,
       req.updated_on,
       src.source_object_id,
       src.source_type,
       src.source_reference,
       src.parent_source_reference,
       src.target_scope_type,
       src.target_scope_key,
       doc.document_id,
       doc.title,
       ver.document_version_id,
       ver.content_uri,
       ver.content_sha256,
       ver.mime_type,
       ver.original_filename,
       ver.byte_size,
       ver.source_modified_on,
       req.processing_profile_code,
       req.processing_instruction,
       req.row_version
  from orac_api.knowledge_ingestion_requests_v req
  join orac_api.knowledge_source_objects_v src
    on src.source_object_id = req.source_object_id
  join orac_api.knowledge_documents_v doc
    on doc.document_id = req.document_id
  join orac_api.knowledge_document_versions_v ver
    on ver.document_version_id = req.document_version_id;
--rollback drop view orac_code.knowledge_ingestion_requests_v;
