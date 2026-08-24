--liquibase formatted sql

--changeset clive:create_package_body_orac_api_knowledge_document_version_tags_tapi context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
create or replace package body orac_api.knowledge_document_version_tags_tapi
as
  procedure ins(
    p_row in out orac_api.knowledge_document_version_tags_v%rowtype
  )
  is
  begin
    insert into orac_api.knowledge_document_version_tags_v (
      document_version_id,
      doc_class_domain_code,
      doc_class_ref_value_code,
      tag_order
    )
    values (
      p_row.document_version_id,
      'DOC_CLASS',
      p_row.doc_class_ref_value_code,
      p_row.tag_order
    );

    p_row.doc_class_domain_code := 'DOC_CLASS';
  end ins;
end knowledge_document_version_tags_tapi;
/
--rollback drop package body orac_api.knowledge_document_version_tags_tapi;
