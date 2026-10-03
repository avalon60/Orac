--liquibase formatted sql

--changeset clive:create_package_body_orac_code_knowledge_scope_validation_api context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: narrow canonical scope validation surface body
create or replace package body orac_code.knowledge_scope_validation_api
as
  function resolve_scope_id(
    p_scope_type in varchar2,
    p_scope_key in varchar2
  ) return number
  is
    l_scope_id number;
  begin
    l_scope_id := orac_code.knowledge_scope_api.resolve_scope_id(
      p_scope_type, p_scope_key
    );
    if scope_status_by_id(l_scope_id) <> 'RAG_USAGE_SCOPE_ELIGIBLE'
    then
      raise_application_error(-20409, 'Knowledge scope is not eligible.');
    end if;
    return l_scope_id;
  end resolve_scope_id;

  function scope_status_by_id(p_knowledge_scope_id in number) return varchar2
  is
  begin
    return orac_code.knowledge_scope_api.scope_status_by_id(p_knowledge_scope_id);
  end scope_status_by_id;

  function scope_status(
    p_scope_type in varchar2,
    p_scope_key  in varchar2
  ) return varchar2
  is
  begin
    return orac_code.knowledge_scope_api.scope_status(p_scope_type, p_scope_key);
  end scope_status;
end knowledge_scope_validation_api;
/
--rollback drop package body orac_code.knowledge_scope_validation_api;
