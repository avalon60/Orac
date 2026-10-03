--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 07-Sep-2026
-- Description: Projects only the current chunk lineage without embedding storage.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_view_orac_code_knowledge_searchable_chunk_content_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.knowledge_searchable_chunk_content_v as
select req.ingestion_request_id,
       src.source_object_id,
       src.source_type,
       src.source_reference,
       src.parent_source_reference,
       doc.document_id,
       scope.knowledge_scope_id,
       scope.scope_type target_scope_type,
       coalesce(project.project_code, scope.plugin_id) target_scope_key,
       doc.title,
       ver.document_version_id,
       ver.content_sha256 revision_content_sha256,
       ver.mime_type,
       ver.source_format_code,
       ver.original_filename,
       ext.extraction_id,
       ext.text_sha256 normalised_text_sha256,
       ext.output_mime_type,
       ext.extractor_code,
       ext.extractor_version,
       ext.extractor_metadata_json,
       chs.chunk_set_id,
       chs.source_artefact_id,
       art.artefact_role_code source_artefact_role_code,
       art.logical_name source_artefact_logical_name,
       art.media_type source_artefact_media_type,
       art.content_sha256 source_artefact_sha256,
       art.member_ordinal source_artefact_ordinal,
       json_value(art.metadata_json, '$.sheet_name' returning varchar2(255)) source_sheet_name,
       json_value(art.metadata_json, '$.table_name' returning varchar2(255)) source_table_name,
       json_value(art.metadata_json, '$.source_cell_range' returning varchar2(100)) source_member_cell_range,
       json_query(art.metadata_json, '$.header_rows' returning clob) source_header_rows_json,
       json_value(art.metadata_json, '$.hidden_sheet' returning varchar2(5)) source_hidden_sheet,
       json_value(chn.chunk_metadata_json, '$.source_row_start' returning number) source_row_start,
       json_value(chn.chunk_metadata_json, '$.source_row_end' returning number) source_row_end,
       json_value(chn.chunk_metadata_json, '$.source_cell_range' returning varchar2(100)) source_chunk_cell_range,
       chn.chunk_id,
       chn.chunk_no,
       chn.span_start,
       chn.span_end,
       chn.token_count,
       chn.content_sha256 chunk_content_sha256,
       chn.chunk_text,
       chn.chunk_metadata_json,
       (
         select json_arrayagg(
                  link.doc_class_ref_value_code
                  order by link.tag_order
                  returning clob
                )
           from orac_api.knowledge_document_version_tags_v link
          where link.document_version_id = ver.document_version_id
            and link.doc_class_domain_code = 'DOC_CLASS'
       ) classification_tags_json,
       req.processing_profile_code,
       req.completed_on,
       chn.created_on
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
   and ver.document_version_id = doc.current_document_version_id
  join orac_api.knowledge_extractions_v ext
    on ext.document_version_id = ver.document_version_id
  join orac_api.knowledge_chunk_sets_v chs
    on chs.extraction_id = ext.extraction_id
  left join orac_api.knowledge_artefacts_v art
    on art.extraction_id = chs.extraction_id
   and art.artefact_id = chs.source_artefact_id
  left join orac_code.knowledge_artefact_sets_v artset
    on artset.extraction_id = ext.extraction_id
  join orac_api.knowledge_chunks_v chn
    on chn.chunk_set_id = chs.chunk_set_id
 where req.status_code = 'COMPLETED'
   and scope.retired_on is null
   and orac_code.knowledge_scope_api.scope_status_by_id(scope.knowledge_scope_id) = 'RAG_USAGE_SCOPE_ELIGIBLE'
   and req.stage_code = 'COMPLETED'
   and not exists (
     select 1
       from orac_api.knowledge_chunk_sets_v newer
      where newer.extraction_id = chs.extraction_id
        and nvl(newer.source_artefact_id, -1) =
            nvl(chs.source_artefact_id, -1)
        and newer.chunk_set_id > chs.chunk_set_id
   )
   and (
     (chs.source_artefact_id is null
      and not exists (
        select 1
          from orac_api.knowledge_artefacts_v registered
         where registered.extraction_id = ext.extraction_id
      ))
     or
     (chs.source_artefact_id is not null
      and art.artefact_id is not null
      and artset.complete_yn = 'Y')
   )
   and dbms_lob.getlength(chn.chunk_text) > 0;
--rollback drop view orac_code.knowledge_searchable_chunk_content_v;
