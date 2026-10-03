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
active_profile as (
  select profile.embedding_profile_id,
         profile.profile_version,
         profile.model_digest,
         profile.storage_layout_code,
         model.provider_code,
         model.model_name,
         model.model_revision,
         model.dimensions
    from orac_api.knowledge_embedding_activations_v activation
    join orac_api.knowledge_embedding_profiles_v profile
      on profile.embedding_profile_id = activation.embedding_profile_id
     and profile.purpose_code = activation.purpose_code
     and profile.semantic_yn = 'Y'
     and profile.production_allowed_yn = 'Y'
    join orac_api.knowledge_embedding_models_v model
      on model.embedding_model_id = profile.embedding_model_id
     and model.dimensions > 0
     and profile.storage_layout_code =
         'ORACLE_VECTOR_' || to_char(model.dimensions) || '_FLOAT32_V1'
   where activation.purpose_code = 'KNOWLEDGE_CHUNK_RETRIEVAL'
),
current_chunk_sets as (
  select chs.*
    from orac_api.knowledge_chunk_sets_v chs
   where not exists (
     select 1
       from orac_api.knowledge_chunk_sets_v newer
      where newer.extraction_id = chs.extraction_id
        and nvl(newer.source_artefact_id, -1) =
            nvl(chs.source_artefact_id, -1)
        and newer.chunk_set_id > chs.chunk_set_id
   )
),
artifact_rollup as (
  select req.ingestion_request_id,
         count(distinct ext.extraction_id) as extraction_count,
         count(distinct artf.artefact_id) as artefact_count,
         min(artset.complete_yn) as artefact_set_complete_yn,
         count(distinct chn.chunk_id) as chunk_count,
         count(distinct emb.chunk_vector_embedding_id) as embedded_chunk_count,
         count(distinct case
           when emb.chunk_vector_embedding_id is not null
           then to_char(active.embedding_profile_id)
         end) as embedding_model_shape_count,
         min(case
           when emb.chunk_vector_embedding_id is not null
           then active.model_name
         end) as embedding_model_identifier,
         min(case
           when emb.chunk_vector_embedding_id is not null
           then active.dimensions
         end) as embedding_dimensions
    from orac_api.knowledge_ingestion_requests_v req
    left join orac_api.knowledge_extractions_v ext
      on ext.document_version_id = req.document_version_id
    left join current_chunk_sets chs
      on chs.extraction_id = ext.extraction_id
    left join orac_api.knowledge_artefacts_v artf
      on artf.extraction_id = ext.extraction_id
    left join orac_code.knowledge_artefact_sets_v artset
      on artset.extraction_id = ext.extraction_id
    left join orac_api.knowledge_chunks_v chn
      on chn.chunk_set_id = chs.chunk_set_id
    left join active_profile active
      on 1 = 1
    left join orac_api.knowledge_chunk_vector_embeddings_v emb
      on emb.chunk_id = chn.chunk_id
     and emb.embedding_profile_id = active.embedding_profile_id
     and emb.embedding_text_sha256 = chn.content_sha256
     and vector_dimension_count(emb.embedding_vector) = active.dimensions
     and vector_dimension_format(emb.embedding_vector) = 'FLOAT32'
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
       coalesce(project.project_code, scope.plugin_id) target_scope_key,
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
       coalesce(art.artefact_count, 0) as artefact_count,
       case
         when coalesce(art.artefact_count, 0) = 0 then 'Y'
         else coalesce(art.artefact_set_complete_yn, 'N')
       end as artefact_set_complete_yn,
       coalesce(art.chunk_count, 0) as chunk_count,
       coalesce(art.embedded_chunk_count, 0) as embedded_chunk_count,
       case
         when req.status_code = 'COMPLETED'
          and coalesce(art.chunk_count, 0) > 0
          and art.chunk_count = art.embedded_chunk_count
          and art.embedding_model_shape_count = 1
          and (
            coalesce(art.artefact_count, 0) = 0
            or art.artefact_set_complete_yn = 'Y'
          )
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
    on plugin.knowledge_scope_id = scope.knowledge_scope_id
  join orac_api.knowledge_document_versions_v ver
    on ver.document_version_id = req.document_version_id
  left join event_rollup evt
    on evt.ingestion_request_id = req.ingestion_request_id
  left join artifact_rollup art
    on art.ingestion_request_id = req.ingestion_request_id;
--rollback drop view orac_code.knowledge_ingestion_requests_v;
