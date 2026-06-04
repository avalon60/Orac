-- __author__: clive
-- __date__: 2026-06-03
-- __description__: ORAC_CODE API body for plugin database deployment state

create or replace package body orac_code.plugin_db_deployment_api as
  procedure record_status(
    p_plugin_id           in  orac_api.plugin_db_deployments_v.plugin_id%type,
    p_plugin_version      in  orac_api.plugin_db_deployments_v.plugin_version%type,
    p_schema_name         in  orac_api.plugin_db_deployments_v.schema_name%type,
    p_deployment_checksum in  orac_api.plugin_db_deployments_v.deployment_checksum%type,
    p_deployment_status   in  orac_api.plugin_db_deployments_v.deployment_status%type,
    p_error_message       in  orac_api.plugin_db_deployments_v.error_message%type default null,
    p_log_path            in  orac_api.plugin_db_deployments_v.log_path%type default null,
    p_row_version         out orac_api.plugin_db_deployments_v.row_version%type
  )
  is
    l_row orac_api.plugin_db_deployments_v%rowtype;
  begin
    begin
      select *
        into l_row
        from orac_api.plugin_db_deployments_v
       where plugin_id = p_plugin_id
         and plugin_version = p_plugin_version
         and schema_name = lower(p_schema_name)
         and deployment_checksum = p_deployment_checksum;

      l_row.deployment_status := p_deployment_status;
      if p_deployment_status in ('succeeded', 'failed')
      then
        l_row.completed_on := systimestamp;
      end if;
      l_row.error_message := p_error_message;
      l_row.log_path := p_log_path;

      orac_api.plugin_db_deployments_tapi.upd(
        p_plugin_db_deployment_id => l_row.plugin_db_deployment_id,
        p_row                     => l_row
      );
      p_row_version := l_row.row_version;
    exception
      when no_data_found then
        l_row.plugin_id := p_plugin_id;
        l_row.plugin_version := p_plugin_version;
        l_row.schema_name := lower(p_schema_name);
        l_row.deployment_checksum := p_deployment_checksum;
        l_row.deployment_status := p_deployment_status;
        l_row.started_on := systimestamp;
        if p_deployment_status in ('succeeded', 'failed')
        then
          l_row.completed_on := systimestamp;
        end if;
        l_row.error_message := p_error_message;
        l_row.log_path := p_log_path;

        orac_api.plugin_db_deployments_tapi.ins(
          p_row => l_row
        );
        p_row_version := l_row.row_version;
    end;
  end record_status;

  function is_deployed(
    p_plugin_id           in  orac_api.plugin_db_deployments_v.plugin_id%type,
    p_plugin_version      in  orac_api.plugin_db_deployments_v.plugin_version%type,
    p_schema_name         in  orac_api.plugin_db_deployments_v.schema_name%type,
    p_deployment_checksum in  orac_api.plugin_db_deployments_v.deployment_checksum%type
  ) return varchar2
  is
    l_deployment_count number;
  begin
    select count(*)
      into l_deployment_count
      from orac_api.plugin_db_deployments_v
     where plugin_id = p_plugin_id
       and plugin_version = p_plugin_version
       and schema_name = lower(p_schema_name)
       and deployment_checksum = p_deployment_checksum
       and deployment_status = 'succeeded';

    if l_deployment_count > 0
    then
      return 'Y';
    end if;

    return 'N';
  end is_deployed;
end plugin_db_deployment_api;
/
