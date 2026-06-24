--liquibase formatted sql

--changeset clive:create_package_body_orac_code_package_body_restore_recovery_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-23
-- __description__: controlled post-restore recovery safety API body

create or replace package body orac_code.restore_recovery_api as
  gc_recovery_status constant varchar2(32 char) := 'recovery_pending';
  gc_reinstall_message constant varchar2(4000 char) :=
    'Restored from backup; reinstall plugin to verify local files, dependencies, database assets, and APEX apps.';

  procedure quarantine_apex_apps
  is
    l_row orac_api.plugin_apex_apps_v%rowtype;
  begin
    for app_rec in (
      select *
        from orac_api.plugin_apex_apps_v
    )
    loop
      l_row := app_rec;
      l_row.installed_app_id := null;
      l_row.install_status := 'pending';
      l_row.last_error_message := gc_reinstall_message;
      l_row.enabled := 'N';

      orac_api.plugin_apex_apps_tapi.upd(
        p_plugin_apex_app_id => l_row.plugin_apex_app_id,
        p_row                => l_row
      );
    end loop;
  end quarantine_apex_apps;

  procedure quarantine_plugin_registry
  is
    l_row orac_api.plugin_registry_v%rowtype;
  begin
    for plugin_rec in (
      select *
        from orac_api.plugin_registry_v
    )
    loop
      l_row := plugin_rec;
      l_row.installed_path := null;
      l_row.install_status := gc_recovery_status;
      l_row.configuration_status := gc_recovery_status;
      l_row.dependency_status := gc_recovery_status;
      l_row.database_status := gc_recovery_status;
      l_row.readiness_status := gc_recovery_status;
      l_row.enabled := 'N';
      l_row.last_error_code := gc_recovery_status;
      l_row.last_error_message := gc_reinstall_message;

      orac_api.plugin_registry_tapi.upd(
        p_plugin_registry_id => l_row.plugin_registry_id,
        p_row                => l_row
      );
    end loop;
  end quarantine_plugin_registry;

  procedure quarantine_plugin_state
  is
  begin
    quarantine_apex_apps;
    quarantine_plugin_registry;
  end quarantine_plugin_state;
end restore_recovery_api;
/

--rollback drop package body orac_code.restore_recovery_api;
