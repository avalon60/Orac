--liquibase formatted sql

--changeset clive:create_view_orac_api_knowledge_documents_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_documents_v as
select document_id,
       source_object_id,
       title,
       current_document_version_id,
       created_by,
       created_on,
       updated_by,
       updated_on,
       row_version
  from orac_core.knowledge_documents;
--rollback drop view orac_api.knowledge_documents_v;
