-- Author: Clive Bostock
-- Date: 13-Sep-2026
-- Purpose: Exercise schema-less removal, fencing, retirement and reinstall using rollback-only fixtures.
-- Usage: sql -S -name orac-db @resources/db/acceptance/plugin_removal_lifecycle.sql
-- Requires the clean-build schema. Does not exercise external resource cleanup.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

whenever sqlerror exit failure rollback
set define off
set serveroutput on

declare
  l_plugin orac_api.plugin_registry_v%rowtype;
  l_old_registry_id number;
  l_old_scope_id number;
  l_operation varchar2(32 char) := lower(rawtohex(sys_guid()));
  l_count number;
  l_denied boolean;
  l_pending_removal exception;
  l_cleanup_incomplete exception;
  pragma exception_init(l_pending_removal, -20073);
  pragma exception_init(l_cleanup_incomplete, -20072);

  procedure assert_true(p_condition in boolean, p_message in varchar2) is
  begin
    if p_condition is null or not p_condition
    then
      raise_application_error(-20980, p_message);
    end if;
  end assert_true;

  procedure register_fixture is
  begin
    l_plugin.plugin_registry_id := null;
    l_plugin.knowledge_scope_id := null;
    l_plugin.plugin_name := 'Rollback-only removal fixture';
    l_plugin.plugin_version := '1.0.0';
    l_plugin.runtime_mode := 'on_demand';
    l_plugin.manifest_hash := rpad('a', 64, 'a');
    l_plugin.package_hash := rpad('b', 64, 'b');
    l_plugin.install_source_type := 'source';
    l_plugin.install_source_ref := 'rollback-only-fixture';
    l_plugin.dependency_fingerprint := rpad('c', 64, 'c');
    l_plugin.command_dependency_fingerprint := rpad('d', 64, 'd');
    l_plugin.command_prerequisite_status := 'not_applicable';
    l_plugin.install_status := 'success';
    l_plugin.configuration_status := 'not_required';
    l_plugin.dependency_status := 'not_required';
    l_plugin.database_status := 'not_required';
    l_plugin.readiness_status := 'success';
    l_plugin.enabled := 'Y';
    l_plugin.database_schemas_summary := json('[]');
    orac_api.plugin_registry_tapi.ins(l_plugin);
  end register_fixture;
begin
  -- A unique fixture prevents interference with real or concurrent registrations.
  l_plugin.plugin_id := 'removal_acceptance_' || lower(rawtohex(sys_guid()));
  register_fixture;
  l_old_registry_id := l_plugin.plugin_registry_id;
  l_old_scope_id := l_plugin.knowledge_scope_id;

  orac_code.plugin_registry_api.set_enabled(l_plugin.plugin_id, 'N');
  orac_code.plugin_registry_api.set_enabled(l_plugin.plugin_id, 'Y');
  orac_code.plugin_registry_api.begin_removal(
    l_plugin.plugin_id, l_old_registry_id, l_operation, 'DROP',
    'ROLLBACK_ONLY_NO_EXTERNAL_RESOURCES',
    json('{"schemas":[],"applications":[],"paths":[]}'),
    'REMOVAL_ACCEPTANCE'
  );

  select count(*) into l_count from orac_code.plugin_registry_v
   where plugin_registry_id = l_old_registry_id and enabled = 'N'
     and removal_id = l_operation;
  assert_true(l_count = 1, 'Removal did not disable and fence the exact row.');
  assert_true(
    orac_code.knowledge_scope_api.scope_status_by_id(l_old_scope_id)
      <> 'RAG_USAGE_SCOPE_ELIGIBLE',
    'Pending removal scope remains eligible.'
  );

  l_denied := false;
  begin
    orac_code.plugin_registry_api.set_enabled(l_plugin.plugin_id, 'Y');
  exception
    when l_pending_removal then l_denied := true;
  end;
  assert_true(l_denied, 'Enable revived a pending removal.');

  l_denied := false;
  begin
    orac_code.plugin_registry_api.finalize_removal(l_operation, l_old_registry_id);
  exception
    when l_cleanup_incomplete then l_denied := true;
  end;
  assert_true(l_denied, 'Finalisation accepted missing cleanup.');
  select count(*) into l_count from orac_code.plugin_registry_v
   where plugin_registry_id = l_old_registry_id and removal_id = l_operation;
  assert_true(l_count = 1, 'Failed finalisation lost the durable fence.');

  -- This synthetic fixture owns no external resources, paths or secrets.
  orac_code.plugin_registry_api.checkpoint_removal(
    l_operation, l_old_registry_id, json('{}'), 'Y', 'Y'
  );
  orac_code.plugin_registry_api.finalize_removal(l_operation, l_old_registry_id);
  select count(*) into l_count from orac_code.plugin_registry_v
   where plugin_registry_id = l_old_registry_id;
  assert_true(l_count = 0, 'Finalisation retained the operational row.');
  select count(*) into l_count from orac_api.knowledge_scopes_v
   where knowledge_scope_id = l_old_scope_id and retired_on is not null
     and plugin_id = l_plugin.plugin_id;
  assert_true(l_count = 1, 'Finalisation lost historical scope attribution.');

  register_fixture;
  assert_true(l_plugin.plugin_registry_id <> l_old_registry_id,
              'Reinstall reused the registry key.');
  assert_true(l_plugin.knowledge_scope_id <> l_old_scope_id,
              'Reinstall adopted historical scope.');
  orac_code.plugin_registry_api.finalize_removal(l_operation, l_old_registry_id);
  select count(*) into l_count from orac_code.plugin_registry_v
   where plugin_registry_id = l_plugin.plugin_registry_id and enabled = 'Y';
  assert_true(l_count = 1, 'Old completion retry affected the successor.');

  rollback;
  dbms_output.put_line('PLUGIN_REMOVAL_LIFECYCLE_ROLLED_BACK');
exception
  when others then
    rollback;
    raise;
end;
/
rollback;
