--liquibase formatted sql

--changeset clive:create_package_body_orac_plugin_knowledge_scope_validation_api context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: plugin bridge body for canonical scope validation only
create or replace package body orac_plugin.knowledge_scope_validation_api
as
  function resolve_scope_id(
    p_scope_type in varchar2,
    p_scope_key in varchar2
  ) return number
  is
  begin
    return orac_code.knowledge_scope_validation_api.resolve_scope_id(
      p_scope_type, p_scope_key
    );
  end resolve_scope_id;

  function scope_status_by_id(p_knowledge_scope_id in number) return varchar2
  is
  begin
    return orac_code.knowledge_scope_validation_api.scope_status_by_id(
      p_knowledge_scope_id
    );
  end scope_status_by_id;

  function scope_status(
    p_scope_type in varchar2,
    p_scope_key  in varchar2
  ) return varchar2
  is
  begin
    return orac_code.knowledge_scope_validation_api.scope_status(
             p_scope_type, p_scope_key
           );
  end scope_status;
end knowledge_scope_validation_api;
/
--rollback drop package body orac_plugin.knowledge_scope_validation_api;
