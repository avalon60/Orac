--liquibase formatted sql

--changeset clive:create_package_body_orac_code_knowledge_scope_api context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-20
-- __description__: canonical knowledge scope synchronisation and resolution body
create or replace package body orac_code.knowledge_scope_api
as
  procedure synchronise_project_scope(
    p_project_id in orac_api.project_registry_v.project_id%type
  )
  is
    l_parent_count number;
    l_row          orac_api.knowledge_scopes_v%rowtype;
  begin
    select count(*)
      into l_parent_count
      from orac_api.project_registry_v
     where project_id = p_project_id;

    if l_parent_count <> 1
    then
      raise_application_error(-20055, 'RAG_USAGE_SCOPE_UNKNOWN');
    end if;

    begin
      select *
        into l_row
        from orac_api.knowledge_scopes_v
       where project_id = p_project_id;
      return;
    exception
      when no_data_found then
        null;
    end;

    l_row.scope_type := 'PROJECT';
    l_row.project_id := p_project_id;
    orac_api.knowledge_scopes_tapi.ins(l_row);
  exception
    when dup_val_on_index then
      null;
  end synchronise_project_scope;

  procedure synchronise_plugin_scope(
    p_plugin_registry_id in orac_api.plugin_registry_v.plugin_registry_id%type
  )
  is
    l_parent_count number;
    l_row          orac_api.knowledge_scopes_v%rowtype;
  begin
    select count(*)
      into l_parent_count
      from orac_api.plugin_registry_v
     where plugin_registry_id = p_plugin_registry_id;

    if l_parent_count <> 1
    then
      raise_application_error(-20055, 'RAG_USAGE_SCOPE_UNKNOWN');
    end if;

    begin
      select *
        into l_row
        from orac_api.knowledge_scopes_v
       where plugin_registry_id = p_plugin_registry_id;
      return;
    exception
      when no_data_found then
        null;
    end;

    l_row.scope_type := 'PLUGIN';
    l_row.plugin_registry_id := p_plugin_registry_id;
    orac_api.knowledge_scopes_tapi.ins(l_row);
  exception
    when dup_val_on_index then
      null;
  end synchronise_plugin_scope;

  function resolve_scope_id(
    p_scope_type in varchar2,
    p_scope_key  in varchar2
  ) return number
  is
    l_scope_id number;
  begin
    if upper(trim(p_scope_type)) = 'PROJECT'
    then
      select scope.knowledge_scope_id
        into l_scope_id
        from orac_api.knowledge_scopes_v scope
        join orac_api.project_registry_v project
          on project.project_id = scope.project_id
       where scope.scope_type = 'PROJECT'
         and project.project_code = trim(p_scope_key);
    elsif upper(trim(p_scope_type)) = 'PLUGIN'
    then
      select scope.knowledge_scope_id
        into l_scope_id
        from orac_api.knowledge_scopes_v scope
        join orac_api.plugin_registry_v plugin
          on plugin.plugin_registry_id = scope.plugin_registry_id
       where scope.scope_type = 'PLUGIN'
         and plugin.plugin_id = trim(p_scope_key);
    else
      raise no_data_found;
    end if;

    return l_scope_id;
  exception
    when no_data_found then
      return null;
  end resolve_scope_id;

  function scope_status(
    p_scope_type in varchar2,
    p_scope_key  in varchar2
  ) return varchar2
  is
    l_status varchar2(100 char);
  begin
    if upper(trim(p_scope_type)) = 'PROJECT'
    then
      select case when project.active_yn = 'Y'
                  then 'RAG_USAGE_SCOPE_ELIGIBLE'
                  else 'RAG_USAGE_SCOPE_INACTIVE'
             end
        into l_status
        from orac_api.knowledge_scopes_v scope
        join orac_api.project_registry_v project
          on project.project_id = scope.project_id
       where scope.scope_type = 'PROJECT'
         and project.project_code = trim(p_scope_key);
    elsif upper(trim(p_scope_type)) = 'PLUGIN'
    then
      select case
               when plugin.enabled <> 'Y' then 'RAG_USAGE_SCOPE_INACTIVE'
               when plugin.install_status = 'success'
                and plugin.configuration_status in ('success', 'not_required')
                and plugin.dependency_status in ('success', 'not_required')
                and plugin.database_status in (
                      'deployed', 'already_deployed', 'not_required', 'optional_missing'
                    )
                and plugin.readiness_status = 'success'
               then 'RAG_USAGE_SCOPE_ELIGIBLE'
               else 'RAG_USAGE_SCOPE_INELIGIBLE'
             end
        into l_status
        from orac_api.knowledge_scopes_v scope
        join orac_api.plugin_registry_v plugin
          on plugin.plugin_registry_id = scope.plugin_registry_id
       where scope.scope_type = 'PLUGIN'
         and plugin.plugin_id = trim(p_scope_key);
    else
      return 'RAG_USAGE_SCOPE_UNKNOWN';
    end if;

    return l_status;
  exception
    when no_data_found then
      return 'RAG_USAGE_SCOPE_UNKNOWN';
  end scope_status;
end knowledge_scope_api;
/
--rollback drop package body orac_code.knowledge_scope_api;
