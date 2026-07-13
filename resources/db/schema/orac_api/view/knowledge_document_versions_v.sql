--liquibase formatted sql

--changeset clive:create_view_orac_api_knowledge_document_versions_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_document_versions_v as
select document_version_id,
       document_id,
       source_object_id,
       content_sha256,
       content_uri,
       mime_type,
       original_filename,
       byte_size,
       source_modified_on,
       created_by,
       created_on,
       updated_by,
       updated_on,
       row_version
  from orac_core.knowledge_document_versions;
--rollback drop view orac_api.knowledge_document_versions_v;
