--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_package_spec_plugin_service_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: Orac-owned plugin service policy, status, and lease API

create or replace package orac_code.plugin_service_api as
  procedure register_service(
    p_plugin_id       in orac_api.plugin_services_v.plugin_id%type,
    p_service_code    in orac_api.plugin_services_v.service_code%type,
    p_service_name    in orac_api.plugin_services_v.service_name%type,
    p_entry_point     in orac_api.plugin_services_v.entry_point%type,
    p_execution_model in orac_api.plugin_services_v.execution_model%type,
    p_manifest_policy in orac_api.plugin_services_v.manifest_policy%type
  );

  procedure set_service_policy(
    p_plugin_id    in orac_api.plugin_services_v.plugin_id%type,
    p_service_code in orac_api.plugin_services_v.service_code%type,
    p_policy       in orac_api.plugin_services_v.policy_override%type,
    p_row_version  in orac_api.plugin_services_v.row_version%type
  );

  function try_acquire_service_lease(
    p_plugin_id     in orac_api.plugin_services_v.plugin_id%type,
    p_service_code  in orac_api.plugin_services_v.service_code%type,
    p_owner_id      in orac_api.plugin_services_v.owner_id%type,
    p_lease_seconds in number
  ) return varchar2;

  function heartbeat_service_lease(
    p_plugin_id     in orac_api.plugin_services_v.plugin_id%type,
    p_service_code  in orac_api.plugin_services_v.service_code%type,
    p_owner_id      in orac_api.plugin_services_v.owner_id%type,
    p_lease_token   in orac_api.plugin_services_v.lease_token%type,
    p_lease_seconds in number
  ) return number;

  function release_service_lease(
    p_plugin_id    in orac_api.plugin_services_v.plugin_id%type,
    p_service_code in orac_api.plugin_services_v.service_code%type,
    p_owner_id     in orac_api.plugin_services_v.owner_id%type,
    p_lease_token  in orac_api.plugin_services_v.lease_token%type
  ) return number;

  function mark_service_state(
    p_plugin_id          in orac_api.plugin_services_v.plugin_id%type,
    p_service_code       in orac_api.plugin_services_v.service_code%type,
    p_owner_id           in orac_api.plugin_services_v.owner_id%type,
    p_lease_token        in orac_api.plugin_services_v.lease_token%type,
    p_state              in orac_api.plugin_services_v.current_state%type,
    p_last_error_message in orac_api.plugin_services_v.last_error_message%type default null,
    p_touch_tick         in varchar2 default 'N'
  ) return number;
end plugin_service_api;
/
--rollback drop package orac_code.plugin_service_api;
