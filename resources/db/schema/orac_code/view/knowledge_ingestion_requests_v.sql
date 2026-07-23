--liquibase formatted sql

--changeset clive:create_view_orac_code_knowledge_ingestion_requests_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.knowledge_ingestion_requests_v as
with event_rollup as (
  select ingestion_request_id,
         min(case when event_type = 'submitted' then event_ts end) as accepted_on,
         min(case when event_type = 'claimed' then event_ts end) as claimed_on,
         max(event_ts) as latest_event_on
    from orac_api.knowledge_ingestion_events_v
   group by ingestion_request_id
),
artifact_rollup as (
  select req.ingestion_request_id,
         count(distinct ext.extraction_id) as extraction_count,
         count(distinct chn.chunk_id) as chunk_count,
         count(distinct emb.chunk_embedding_id) as embedded_chunk_count,
         count(distinct modl.model_name || ':' || to_char(modl.dimensions)) as embedding_model_shape_count,
         min(modl.model_name) as embedding_model_identifier,
         min(modl.dimensions) as embedding_dimensions
    from orac_api.knowledge_ingestion_requests_v req
    left join orac_api.knowledge_extractions_v ext
      on ext.document_version_id = req.document_version_id
    left join orac_api.knowledge_chunk_sets_v chs
      on chs.extraction_id = ext.extraction_id
    left join orac_api.knowledge_chunks_v chn
      on chn.chunk_set_id = chs.chunk_set_id
    left join orac_api.knowledge_chunk_embeddings_v emb
      on emb.chunk_id = chn.chunk_id
    left join orac_api.knowledge_embedding_models_v modl
      on modl.embedding_model_id = emb.embedding_model_id
   group by req.ingestion_request_id
)
select req.ingestion_request_id,
       req.status_code,
       case req.status_code
         when 'QUEUED' then 'Queued - awaiting Core worker claim'
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
       evt.accepted_on,
       evt.claimed_on,
       evt.latest_event_on,
       req.completed_on,
       req.created_on,
       req.updated_on,
       src.source_object_id,
       src.source_type,
       src.source_reference,
       src.parent_source_reference,
       scope.scope_type target_scope_type,
       coalesce(project.project_code, plugin.plugin_id) target_scope_key,
       doc.document_id,
       doc.title,
       ver.document_version_id,
       ver.content_uri,
       ver.content_sha256,
       ver.mime_type,
       ver.original_filename,
       ver.byte_size,
       ver.source_modified_on,
       coalesce(art.extraction_count, 0) as extraction_count,
       coalesce(art.chunk_count, 0) as chunk_count,
       coalesce(art.embedded_chunk_count, 0) as embedded_chunk_count,
       case
         when req.status_code = 'COMPLETED'
          and coalesce(art.chunk_count, 0) > 0
          and art.chunk_count = art.embedded_chunk_count
          and art.embedding_model_shape_count = 1
         then 'Y'
         else 'N'
       end as searchable_yn,
       art.embedding_model_identifier,
       art.embedding_dimensions,
       req.processing_profile_code,
       req.processing_instruction,
       req.row_version
  from orac_api.knowledge_ingestion_requests_v req
  join orac_api.knowledge_source_objects_v src
    on src.source_object_id = req.source_object_id
  join orac_api.knowledge_documents_v doc
    on doc.document_id = req.document_id
  join orac_api.knowledge_scopes_v scope
    on scope.knowledge_scope_id = src.knowledge_scope_id
  left join orac_api.project_registry_v project
    on project.project_id = scope.project_id
  left join orac_api.plugin_registry_v plugin
    on plugin.plugin_registry_id = scope.plugin_registry_id
  join orac_api.knowledge_document_versions_v ver
    on ver.document_version_id = req.document_version_id
  left join event_rollup evt
    on evt.ingestion_request_id = req.ingestion_request_id
  left join artifact_rollup art
    on art.ingestion_request_id = req.ingestion_request_id;
--rollback drop view orac_code.knowledge_ingestion_requests_v;
