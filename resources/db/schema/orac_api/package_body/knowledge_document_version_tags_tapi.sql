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
      document_version_id, knowledge_tag_id, tag_order
    ) values (
      p_row.document_version_id, p_row.knowledge_tag_id, p_row.tag_order
    )
    returning knowledge_document_version_tag_id
         into p_row.knowledge_document_version_tag_id;
  end ins;
end knowledge_document_version_tags_tapi;
/
--rollback drop package body orac_api.knowledge_document_version_tags_tapi;
