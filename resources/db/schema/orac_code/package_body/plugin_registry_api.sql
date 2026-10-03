--liquibase formatted sql

--changeset clive:create_package_body_orac_code_package_body_plugin_registry_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-07
-- __description__: controlled plugin installation registry API body

create or replace package body orac_code.plugin_registry_api as
  procedure upsert_plugin(
    p_plugin_id                in orac_api.plugin_registry_v.plugin_id%type,
    p_plugin_name              in orac_api.plugin_registry_v.plugin_name%type,
    p_plugin_version           in orac_api.plugin_registry_v.plugin_version%type,
    p_runtime_mode             in orac_api.plugin_registry_v.runtime_mode%type,
    p_manifest_hash            in orac_api.plugin_registry_v.manifest_hash%type,
    p_package_hash             in orac_api.plugin_registry_v.package_hash%type,
    p_install_source_type      in orac_api.plugin_registry_v.install_source_type%type,
    p_install_source_ref       in orac_api.plugin_registry_v.install_source_ref%type,
    p_installed_path           in orac_api.plugin_registry_v.installed_path%type,
    p_config_path              in orac_api.plugin_registry_v.config_path%type,
    p_capabilities_summary     in orac_api.plugin_registry_v.capabilities_summary%type,
    p_entitlements_summary     in orac_api.plugin_registry_v.entitlements_summary%type,
    p_database_schemas_summary in orac_api.plugin_registry_v.database_schemas_summary%type,
    p_dependency_declarations  in orac_api.plugin_registry_v.dependency_declarations%type,
    p_dependency_fingerprint   in orac_api.plugin_registry_v.dependency_fingerprint%type,
    p_command_dependency_declarations in orac_api.plugin_registry_v.command_dependency_declarations%type,
    p_command_dependency_fingerprint in orac_api.plugin_registry_v.command_dependency_fingerprint%type,
    p_command_prerequisite_status in orac_api.plugin_registry_v.command_prerequisite_status%type,
    p_command_dependency_report in orac_api.plugin_registry_v.command_dependency_report%type,
    p_install_status           in orac_api.plugin_registry_v.install_status%type,
    p_configuration_status     in orac_api.plugin_registry_v.configuration_status%type,
    p_dependency_status        in orac_api.plugin_registry_v.dependency_status%type,
    p_database_status          in orac_api.plugin_registry_v.database_status%type,
    p_readiness_status         in orac_api.plugin_registry_v.readiness_status%type,
    p_enabled                  in orac_api.plugin_registry_v.enabled%type,
    p_ui_icon_class            in orac_api.plugin_registry_v.ui_icon_class%type default null,
    p_ui_accent_class          in orac_api.plugin_registry_v.ui_accent_class%type default null,
    p_last_error_code          in orac_api.plugin_registry_v.last_error_code%type default null,
    p_last_error_message       in orac_api.plugin_registry_v.last_error_message%type default null
  )
  is
    l_row orac_api.plugin_registry_v%rowtype;
  begin
    begin
      select *
        into l_row
        from orac_api.plugin_registry_v
       where plugin_id = p_plugin_id;
    exception
      when no_data_found then
        null;
    end;

    l_row.plugin_id := p_plugin_id;
    l_row.plugin_name := p_plugin_name;
    l_row.plugin_version := p_plugin_version;
    l_row.runtime_mode := p_runtime_mode;
    l_row.manifest_hash := p_manifest_hash;
    l_row.package_hash := p_package_hash;
    l_row.install_source_type := p_install_source_type;
    l_row.install_source_ref := p_install_source_ref;
    l_row.installed_path := p_installed_path;
    l_row.config_path := p_config_path;
    l_row.capabilities_summary := p_capabilities_summary;
    l_row.entitlements_summary := p_entitlements_summary;
    l_row.database_schemas_summary := p_database_schemas_summary;
    l_row.ui_icon_class := p_ui_icon_class;
    l_row.ui_accent_class := p_ui_accent_class;
    l_row.dependency_declarations := p_dependency_declarations;
    l_row.dependency_fingerprint := p_dependency_fingerprint;
    l_row.command_dependency_declarations := p_command_dependency_declarations;
    l_row.command_dependency_fingerprint := p_command_dependency_fingerprint;
    l_row.command_prerequisite_status := p_command_prerequisite_status;
    l_row.command_dependency_report := p_command_dependency_report;
    l_row.install_status := p_install_status;
    l_row.configuration_status := p_configuration_status;
    l_row.dependency_status := p_dependency_status;
    l_row.database_status := p_database_status;
    l_row.readiness_status := p_readiness_status;
    l_row.enabled := p_enabled;
    l_row.last_error_code := p_last_error_code;
    l_row.last_error_message := p_last_error_message;

    if l_row.plugin_registry_id is null
    then
      orac_api.plugin_registry_tapi.ins(l_row);
    else
      orac_api.plugin_registry_tapi.upd(l_row.plugin_registry_id, l_row);
    end if;
    orac_code.knowledge_scope_api.synchronise_plugin_scope(
      l_row.plugin_registry_id
    );
  end upsert_plugin;

  procedure update_command_prerequisite_status(
    p_plugin_id in orac_api.plugin_registry_v.plugin_id%type,
    p_command_prerequisite_status in orac_api.plugin_registry_v.command_prerequisite_status%type,
    p_command_dependency_report in orac_api.plugin_registry_v.command_dependency_report%type
  )
  is
  begin
    if p_command_prerequisite_status not in (
         'not_applicable', 'success', 'degraded', 'failed'
       )
    then
      raise_application_error(-20042, 'Invalid command prerequisite status.');
    end if;
    update orac_api.plugin_registry_v
       set command_prerequisite_status = p_command_prerequisite_status,
           command_dependency_report = p_command_dependency_report
     where plugin_id = p_plugin_id;
    if sql%rowcount <> 1
    then
      raise_application_error(-20043, 'Plugin registry row was not found.');
    end if;
  end update_command_prerequisite_status;
  procedure set_enabled(p_plugin_id in varchar2, p_enabled in varchar2) is
    l_row orac_api.plugin_registry_v%rowtype;
    l_audit_id number;
    l_audit_version number;
    l_provenance json;
  begin
    savepoint set_plugin_enablement;
    if p_enabled is null or p_enabled not in ('Y', 'N')
    then
      raise_application_error(-20075, 'Enablement must be Y or N.');
    end if;
    select * into l_row from orac_api.plugin_registry_v where plugin_id = p_plugin_id for update;
    if p_enabled = 'Y' and (
      l_row.install_status <> 'success'
      or l_row.configuration_status not in ('success', 'not_required')
      or l_row.dependency_status not in ('success', 'not_required')
      or l_row.command_prerequisite_status not in ('not_applicable', 'success', 'degraded')
      or l_row.database_status not in ('deployed', 'already_deployed', 'not_required', 'optional_missing')
      or l_row.readiness_status <> 'success')
    then
      raise_application_error(-20076, 'Plugin readiness does not permit enablement.');
    end if;
    l_row.enabled := p_enabled;
    orac_api.plugin_registry_tapi.upd(l_row.plugin_registry_id, l_row);
    select json_object(
      'plugin_id' value l_row.plugin_id,
      'plugin_version' value l_row.plugin_version,
      'knowledge_scope_id' value l_row.knowledge_scope_id,
      'lifecycle_action' value case p_enabled when 'Y' then 'enable' else 'disable' end,
      'lifecycle_outcome' value 'completed',
      'actor' value sys_context('userenv', 'session_user') returning json)
      into l_provenance from dual;
    orac_code.plugin_audit_api.begin_invocation(
      p_plugin_invocation_id => l_audit_id, p_row_version => l_audit_version,
      p_plugin_id => l_row.plugin_id, p_plugin_name => l_row.plugin_name,
      p_action_type => 'local_mutation', p_provenance_json => l_provenance);
    orac_code.plugin_audit_api.record_execution_event(
      p_plugin_invocation_id => l_audit_id, p_event_type => 'execution_completed',
      p_execution_status => 'completed', p_provenance_json => l_provenance,
      p_row_version => l_audit_version);
  exception
    when no_data_found then
      rollback to set_plugin_enablement;
      raise_application_error(-20043, 'Plugin is not installed; install it instead of enabling it.');
    when others then
      rollback to set_plugin_enablement;
      raise;
  end set_enabled;

  procedure begin_removal(p_plugin_id in varchar2, p_expected_registry_id in number,
    p_removal_id in varchar2, p_schema_disposition in varchar2,
    p_database_identity in varchar2, p_resource_inventory in json, p_confirmed_by in varchar2) is
    l_plugin orac_api.plugin_registry_v%rowtype;
    l_removal orac_api.plugin_removals_v%rowtype;
    l_inventory_bytes number;
  begin
    savepoint begin_plugin_removal;
    if p_removal_id is null or not regexp_like(p_removal_id, '^[0-9a-f]{32}$')
       or p_schema_disposition is null or p_schema_disposition not in ('DROP', 'KEEP')
       or trim(p_database_identity) is null or trim(p_confirmed_by) is null
       or p_resource_inventory is null
    then
      raise_application_error(-20075, 'Explicit removal authorization is required.');
    end if;
    select dbms_lob.getlength(json_serialize(p_resource_inventory returning clob))
      into l_inventory_bytes from dual;
    if l_inventory_bytes > 65536
    then
      raise_application_error(-20075, 'Removal inventory exceeds the bounded authorization size.');
    end if;
    select * into l_plugin from orac_api.plugin_registry_v
     where plugin_id = p_plugin_id and plugin_registry_id = p_expected_registry_id for update;
    l_plugin.enabled := 'N';
    orac_api.plugin_registry_tapi.upd(l_plugin.plugin_registry_id, l_plugin);
    l_removal.removal_id := p_removal_id;
    l_removal.plugin_id := l_plugin.plugin_id;
    l_removal.plugin_registry_id := l_plugin.plugin_registry_id;
    l_removal.knowledge_scope_id := l_plugin.knowledge_scope_id;
    l_removal.plugin_version := l_plugin.plugin_version;
    l_removal.manifest_hash := l_plugin.manifest_hash;
    l_removal.schema_disposition := p_schema_disposition;
    l_removal.database_identity := p_database_identity;
    l_removal.resource_inventory := p_resource_inventory;
    l_removal.confirmed_by := p_confirmed_by;
    orac_api.plugin_removals_tapi.ins(l_removal);
  exception
    when others then
      rollback to begin_plugin_removal;
      raise;
  end begin_removal;

  procedure checkpoint_removal(p_removal_id in varchar2, p_expected_registry_id in number,
    p_checkpoints in json, p_external_complete_yn in varchar2, p_files_complete_yn in varchar2,
    p_error_code in varchar2 default null, p_error_message in varchar2 default null) is
    l_count number;
  begin
    select count(*) into l_count from orac_api.plugin_removals_v removal
      join orac_api.plugin_registry_v plugin on plugin.plugin_registry_id = removal.plugin_registry_id
     where removal.removal_id = p_removal_id and removal.plugin_registry_id = p_expected_registry_id
       and removal.completed_on is null and plugin.enabled = 'N';
    if l_count <> 1
    then
      raise_application_error(-20071, 'Removal target is no longer the authorized installation.');
    end if;
    orac_api.plugin_removals_tapi.checkpoint(p_removal_id, p_checkpoints,
      p_external_complete_yn, p_files_complete_yn, p_error_code, p_error_message);
  end checkpoint_removal;

  procedure finalize_removal(p_removal_id in varchar2, p_expected_registry_id in number) is
    l_plugin orac_api.plugin_registry_v%rowtype;
    l_removal orac_api.plugin_removals_v%rowtype;
    l_unhandled number;
    l_audit_id number;
    l_audit_version number;
    l_provenance json;
  begin
    savepoint finalize_plugin_removal;
    select * into l_removal from orac_api.plugin_removals_v
     where removal_id = p_removal_id and plugin_registry_id = p_expected_registry_id;
    if l_removal.completed_on is not null
    then
      return; -- Never touches a successor registration.
    end if;
    select * into l_plugin from orac_api.plugin_registry_v
     where plugin_registry_id = p_expected_registry_id and plugin_id = l_removal.plugin_id for update;
    if l_plugin.enabled <> 'N' or l_removal.external_complete_yn <> 'Y'
       or l_removal.files_complete_yn <> 'Y'
    then
      raise_application_error(-20072, 'Required plugin cleanup is incomplete.');
    end if;
    select count(*) into l_unhandled
      from json_table(l_plugin.database_schemas_summary, '$[*]'
             columns (schema_name varchar2(128) path '$')) declared
     where not exists (
       select 1 from orac_api.plugin_schema_ownership_v receipt
        where receipt.plugin_registry_id = l_plugin.plugin_registry_id
          and receipt.plugin_id = l_plugin.plugin_id
          and receipt.database_identity = l_removal.database_identity
          and receipt.schema_name = upper(declared.schema_name)
          and receipt.removal_id = p_removal_id
          and receipt.disposition = case l_removal.schema_disposition
                                      when 'KEEP' then 'RETAINED' else 'DROPPED' end
     )
       and not (
         not exists (
           select 1 from orac_api.plugin_schema_ownership_v receipt
            where receipt.plugin_registry_id = l_plugin.plugin_registry_id
              and receipt.schema_name = upper(declared.schema_name)
         )
         and exists (
           select 1 from json_table(l_removal.resource_inventory, '$.database.schemas[*]'
             columns (schema_name varchar2(128) path '$.schema_name',
                      state varchar2(32) path '$.state')) inventory
            where inventory.schema_name = upper(declared.schema_name)
              and inventory.state = 'NOT_PROVISIONED'
         )
       );
    if l_unhandled <> 0
    then
      raise_application_error(-20077, 'Privileged schema disposition evidence is missing.');
    end if;
    orac_api.plugin_services_tapi.delete_for_removal(p_removal_id);
    orac_api.plugin_apex_apps_tapi.delete_for_removal(p_removal_id);
    orac_api.plugin_db_deployments_tapi.delete_for_removal(p_removal_id);
    orac_api.knowledge_scopes_tapi.retire_for_removal(p_removal_id);
    select json_object(
      'plugin_id' value l_removal.plugin_id,
      'plugin_version' value l_removal.plugin_version,
      'lifecycle_action' value 'remove',
      'lifecycle_outcome' value 'completed',
      'removal_id' value p_removal_id,
      'knowledge_scope_id' value l_removal.knowledge_scope_id,
      'actor' value l_removal.confirmed_by,
      'schema_disposition' value l_removal.schema_disposition returning json)
      into l_provenance from dual;
    orac_code.plugin_audit_api.begin_invocation(
      p_plugin_invocation_id => l_audit_id, p_row_version => l_audit_version,
      p_plugin_id => l_removal.plugin_id, p_plugin_name => l_removal.plugin_id,
      p_action_type => 'local_mutation', p_provenance_json => l_provenance);
    orac_code.plugin_audit_api.record_execution_event(
      p_plugin_invocation_id => l_audit_id, p_event_type => 'execution_completed',
      p_execution_status => 'completed', p_provenance_json => l_provenance,
      p_row_version => l_audit_version);
    orac_api.plugin_removals_tapi.complete(p_removal_id);
    orac_api.plugin_registry_tapi.del(p_expected_registry_id);
  exception
    when others then
      rollback to finalize_plugin_removal;
      raise;
  end finalize_removal;
end plugin_registry_api;
/

--rollback drop package body orac_code.plugin_registry_api;
