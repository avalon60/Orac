--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_knowledge_scope_api context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: canonical knowledge scope synchronisation and resolution
create or replace package orac_code.knowledge_scope_api
authid definer
as
  procedure synchronise_project_scope(
    p_project_id in orac_api.project_registry_v.project_id%type
  );

  procedure synchronise_plugin_scope(
    p_plugin_registry_id in orac_api.plugin_registry_v.plugin_registry_id%type
  );

  function resolve_scope_id(
    p_scope_type in varchar2,
    p_scope_key  in varchar2
  ) return number;

  function scope_status(
    p_scope_type in varchar2,
    p_scope_key  in varchar2
  ) return varchar2;
end knowledge_scope_api;
/
--rollback drop package orac_code.knowledge_scope_api;
