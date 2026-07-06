--liquibase formatted sql

--changeset clive:plugin_services_tapi_create_spec stripComments:false endDelimiter:/ runOnChange:true context:core labels:core splitStatements:false

create or replace package orac_api.plugin_services_tapi
authid definer
as
  subtype ty_row is orac_api.plugin_services_v%rowtype;

  procedure ins(
    p_row in out orac_api.plugin_services_v%rowtype
  );

  procedure get(
    p_plugin_service_id in  orac_api.plugin_services_v.plugin_service_id%type,
    p_row               out orac_api.plugin_services_v%rowtype
  );

  procedure get_by_key(
    p_plugin_id    in  orac_api.plugin_services_v.plugin_id%type,
    p_service_code in  orac_api.plugin_services_v.service_code%type,
    p_row          out orac_api.plugin_services_v%rowtype
  );

  procedure upd(
    p_plugin_service_id in     orac_api.plugin_services_v.plugin_service_id%type,
    p_row               in out orac_api.plugin_services_v%rowtype
  );

  procedure try_acquire_lease(
    p_plugin_id     in  orac_api.plugin_services_v.plugin_id%type,
    p_service_code  in  orac_api.plugin_services_v.service_code%type,
    p_owner_id      in  orac_api.plugin_services_v.owner_id%type,
    p_lease_seconds in  number,
    p_lease_token   out orac_api.plugin_services_v.lease_token%type
  );

  function heartbeat_lease(
    p_plugin_id     in orac_api.plugin_services_v.plugin_id%type,
    p_service_code  in orac_api.plugin_services_v.service_code%type,
    p_owner_id      in orac_api.plugin_services_v.owner_id%type,
    p_lease_token   in orac_api.plugin_services_v.lease_token%type,
    p_lease_seconds in number
  ) return number;

  function release_lease(
    p_plugin_id    in orac_api.plugin_services_v.plugin_id%type,
    p_service_code in orac_api.plugin_services_v.service_code%type,
    p_owner_id     in orac_api.plugin_services_v.owner_id%type,
    p_lease_token  in orac_api.plugin_services_v.lease_token%type
  ) return number;

  function mark_state(
    p_plugin_id          in orac_api.plugin_services_v.plugin_id%type,
    p_service_code       in orac_api.plugin_services_v.service_code%type,
    p_owner_id           in orac_api.plugin_services_v.owner_id%type,
    p_lease_token        in orac_api.plugin_services_v.lease_token%type,
    p_state              in orac_api.plugin_services_v.current_state%type,
    p_last_error_message in orac_api.plugin_services_v.last_error_message%type default null,
    p_touch_tick         in varchar2 default 'N'
  ) return number;
end plugin_services_tapi;
/
--rollback drop package orac_api.plugin_services_tapi;
