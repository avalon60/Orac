--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_knowledge_scope_validation_api context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: narrow canonical scope validation surface for the plugin bridge
create or replace package orac_code.knowledge_scope_validation_api
authid definer
as
  function scope_status(
    p_scope_type in varchar2,
    p_scope_key  in varchar2
  ) return varchar2;
end knowledge_scope_validation_api;
/
--rollback drop package orac_code.knowledge_scope_validation_api;
