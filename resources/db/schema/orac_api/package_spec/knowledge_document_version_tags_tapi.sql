--liquibase formatted sql

--changeset clive:create_package_spec_orac_api_knowledge_document_version_tags_tapi context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
create or replace package orac_api.knowledge_document_version_tags_tapi
authid definer
as
  procedure ins(
    p_row in out orac_api.knowledge_document_version_tags_v%rowtype
  );
end knowledge_document_version_tags_tapi;
/
--rollback drop package orac_api.knowledge_document_version_tags_tapi;
