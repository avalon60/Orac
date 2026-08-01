--liquibase formatted sql

--changeset clive:create_package_spec_orac_plugin_knowledge_tag_validation_api context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
create or replace package orac_plugin.knowledge_tag_validation_api
authid definer
as
  function canonical_active_tags(
    p_classification_tags_json in clob,
    p_require_non_empty_yn     in varchar2 default 'N'
  ) return clob;
end knowledge_tag_validation_api;
/
--rollback drop package orac_plugin.knowledge_tag_validation_api;
