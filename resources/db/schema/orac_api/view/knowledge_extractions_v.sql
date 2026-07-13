--liquibase formatted sql

--changeset clive:create_view_orac_api_knowledge_extractions_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_extractions_v as
select extraction_id,
       document_version_id,
       extractor_code,
       extractor_version,
       text_sha256,
       extracted_text,
       created_by,
       created_on,
       updated_by,
       updated_on,
       row_version
  from orac_core.knowledge_extractions;
--rollback drop view orac_api.knowledge_extractions_v;
