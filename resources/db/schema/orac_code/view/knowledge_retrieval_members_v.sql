--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Resolves document, extraction, and normalised member lineage for the retrieval API.

--changeset clive:create_view_orac_code_knowledge_retrieval_members_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.knowledge_retrieval_members_v as
select src.knowledge_scope_id,
       scope.scope_type target_scope_type,
       coalesce(project.project_code, scope.plugin_id) target_scope_key,
       src.source_object_id,
       src.source_type,
       src.source_reference,
       src.parent_source_reference,
       doc.document_id,
       doc.title document_title,
       doc.current_document_version_id,
       doc.retrieval_enabled_yn,
       ver.document_version_id,
       ver.content_sha256 revision_content_sha256,
       ver.mime_type revision_mime_type,
       ver.original_filename,
       ver.byte_size revision_byte_size,
       ver.source_modified_on,
       ver.source_format_code,
       ext.extraction_id,
       ext.text_sha256 normalised_text_sha256,
       ext.output_mime_type,
       ext.extractor_code,
       ext.extractor_version,
       ext.extractor_metadata_json,
       ext.extracted_text legacy_extracted_text,
       artset.member_count output_member_count,
       artset.complete_yn output_set_complete_yn,
       art.artefact_id,
       art.artefact_role_code,
       art.media_type artefact_media_type,
       art.content_sha256 artefact_content_sha256,
       art.storage_key artefact_storage_key,
       art.byte_size artefact_byte_size,
       art.logical_name artefact_logical_name,
       art.member_ordinal,
       art.metadata_json artefact_metadata_json,
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
       case
         when doc.retrieval_enabled_yn = 'Y'
          and exists (
           select 1
             from orac_api.knowledge_ingestion_requests_v req
            where req.document_version_id = ver.document_version_id
              and req.status_code = 'COMPLETED'
              and req.stage_code = 'COMPLETED'
         )
          and (
            artset.complete_yn = 'Y'
            or not exists (
              select 1
                from orac_api.knowledge_artefacts_v registered
               where registered.extraction_id = ext.extraction_id
            )
          )
         then 'Y'
         else 'N'
       end retrieval_eligible_yn
  from orac_api.knowledge_source_objects_v src
  join orac_api.knowledge_scopes_v scope
    on scope.knowledge_scope_id = src.knowledge_scope_id
  left join orac_api.project_registry_v project
    on project.project_id = scope.project_id
  left join orac_api.plugin_registry_v plugin
    on plugin.knowledge_scope_id = scope.knowledge_scope_id
  join orac_api.knowledge_documents_v doc
    on doc.source_object_id = src.source_object_id
  join orac_api.knowledge_document_versions_v ver
    on ver.document_id = doc.document_id
  left join orac_api.knowledge_extractions_v ext
    on ext.document_version_id = ver.document_version_id
  left join orac_code.knowledge_artefact_sets_v artset
    on artset.extraction_id = ext.extraction_id
  left join orac_api.knowledge_artefacts_v art
    on art.extraction_id = ext.extraction_id;
--rollback drop view orac_code.knowledge_retrieval_members_v;
