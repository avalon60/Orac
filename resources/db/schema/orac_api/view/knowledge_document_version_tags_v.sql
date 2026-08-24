--liquibase formatted sql

--changeset clive:create_orac_api_knowledge_document_version_tags_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_document_version_tags_v as
select document_version_id,
       doc_class_domain_code,
       doc_class_ref_value_code,
       tag_order,
       created_by,
       created_on
  from orac_core.knowledge_document_version_tags;
--rollback drop view orac_api.knowledge_document_version_tags_v;
