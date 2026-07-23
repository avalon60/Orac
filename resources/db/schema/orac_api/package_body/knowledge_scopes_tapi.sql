--liquibase formatted sql

--changeset clive:create_package_body_orac_api_knowledge_scopes_tapi context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: controlled insert API body for canonical knowledge scopes
create or replace package body orac_api.knowledge_scopes_tapi
as
  procedure ins(p_row in out orac_api.knowledge_scopes_v%rowtype)
  is
  begin
    insert into orac_api.knowledge_scopes_v
      (scope_type, project_id, plugin_registry_id)
    values
      (p_row.scope_type, p_row.project_id, p_row.plugin_registry_id)
    returning knowledge_scope_id, row_version
         into p_row.knowledge_scope_id, p_row.row_version;
  end ins;
end knowledge_scopes_tapi;
/
--rollback drop package body orac_api.knowledge_scopes_tapi;
