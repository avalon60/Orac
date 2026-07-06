--liquibase formatted sql

--changeset clive:plugin_services_tapi_create_body stripComments:false endDelimiter:/ runOnChange:true context:core labels:core splitStatements:false

create or replace package body orac_api.plugin_services_tapi
as
  procedure ins(
    p_row in out orac_api.plugin_services_v%rowtype
  )
  is
  begin
    insert into orac_api.plugin_services_v
      (
        plugin_id,
        service_code,
        service_name,
        entry_point,
        execution_model,
        manifest_policy,
        policy_override,
        current_state
      )
    values
      (
        p_row.plugin_id,
        p_row.service_code,
        p_row.service_name,
        p_row.entry_point,
        p_row.execution_model,
        p_row.manifest_policy,
        p_row.policy_override,
        p_row.current_state
      )
    returning plugin_service_id, row_version
         into p_row.plugin_service_id, p_row.row_version;
  end ins;

  procedure get(
    p_plugin_service_id in  orac_api.plugin_services_v.plugin_service_id%type,
    p_row               out orac_api.plugin_services_v%rowtype
  )
  is
  begin
    select *
      into p_row
      from orac_api.plugin_services_v
     where plugin_service_id = p_plugin_service_id;
  end get;

  procedure get_by_key(
    p_plugin_id    in  orac_api.plugin_services_v.plugin_id%type,
    p_service_code in  orac_api.plugin_services_v.service_code%type,
    p_row          out orac_api.plugin_services_v%rowtype
  )
  is
  begin
    select *
      into p_row
      from orac_api.plugin_services_v
     where plugin_id = p_plugin_id
       and service_code = p_service_code;
  end get_by_key;

  procedure upd(
    p_plugin_service_id in     orac_api.plugin_services_v.plugin_service_id%type,
    p_row               in out orac_api.plugin_services_v%rowtype
  )
  is
  begin
    update orac_api.plugin_services_v
       set plugin_id           = p_row.plugin_id,
           service_code        = p_row.service_code,
           service_name        = p_row.service_name,
           entry_point         = p_row.entry_point,
           execution_model     = p_row.execution_model,
           manifest_policy     = p_row.manifest_policy,
           policy_override     = p_row.policy_override,
           current_state       = p_row.current_state,
           owner_id            = p_row.owner_id,
           lease_token         = p_row.lease_token,
           lease_expires_on    = p_row.lease_expires_on,
           last_started_on     = p_row.last_started_on,
           last_heartbeat_on   = p_row.last_heartbeat_on,
           last_tick_on        = p_row.last_tick_on,
           last_error_message  = p_row.last_error_message
     where plugin_service_id = p_plugin_service_id
    returning plugin_service_id, row_version
         into p_row.plugin_service_id, p_row.row_version;
  end upd;

  procedure try_acquire_lease(
    p_plugin_id     in  orac_api.plugin_services_v.plugin_id%type,
    p_service_code  in  orac_api.plugin_services_v.service_code%type,
    p_owner_id      in  orac_api.plugin_services_v.owner_id%type,
    p_lease_seconds in  number,
    p_lease_token   out orac_api.plugin_services_v.lease_token%type
  )
  is
    l_lease_token orac_api.plugin_services_v.lease_token%type;
  begin
    p_lease_token := null;
    l_lease_token := lower(rawtohex(sys_guid()));

    update orac_api.plugin_services_v
       set owner_id          = p_owner_id,
           lease_token       = l_lease_token,
           lease_expires_on  = cast(systimestamp as timestamp) + numtodsinterval(p_lease_seconds, 'second'),
           last_started_on   = cast(systimestamp as timestamp),
           last_heartbeat_on = cast(systimestamp as timestamp),
           current_state     = 'starting',
           last_error_message = null
     where plugin_id = p_plugin_id
       and service_code = p_service_code
       and coalesce(policy_override, manifest_policy) <> 'disabled'
       and (
             lease_token is null
             or lease_expires_on is null
             or lease_expires_on <= cast(systimestamp as timestamp)
             or owner_id = p_owner_id
           );

    if sql%rowcount = 1
    then
      p_lease_token := l_lease_token;
    end if;
  end try_acquire_lease;

  function heartbeat_lease(
    p_plugin_id     in orac_api.plugin_services_v.plugin_id%type,
    p_service_code  in orac_api.plugin_services_v.service_code%type,
    p_owner_id      in orac_api.plugin_services_v.owner_id%type,
    p_lease_token   in orac_api.plugin_services_v.lease_token%type,
    p_lease_seconds in number
  ) return number
  is
  begin
    update orac_api.plugin_services_v
       set lease_expires_on  = cast(systimestamp as timestamp) + numtodsinterval(p_lease_seconds, 'second'),
           last_heartbeat_on = cast(systimestamp as timestamp),
           current_state     = case
                                 when current_state in ('starting', 'registered', 'stopped') then 'running'
                                 else current_state
                               end
     where plugin_id = p_plugin_id
       and service_code = p_service_code
       and owner_id = p_owner_id
       and lease_token = p_lease_token
       and lease_expires_on > cast(systimestamp as timestamp);

    return sql%rowcount;
  end heartbeat_lease;

  function release_lease(
    p_plugin_id    in orac_api.plugin_services_v.plugin_id%type,
    p_service_code in orac_api.plugin_services_v.service_code%type,
    p_owner_id     in orac_api.plugin_services_v.owner_id%type,
    p_lease_token  in orac_api.plugin_services_v.lease_token%type
  ) return number
  is
  begin
    update orac_api.plugin_services_v
       set owner_id         = null,
           lease_token      = null,
           lease_expires_on = null,
           current_state    = 'stopped'
     where plugin_id = p_plugin_id
       and service_code = p_service_code
       and owner_id = p_owner_id
       and lease_token = p_lease_token;

    return sql%rowcount;
  end release_lease;

  function mark_state(
    p_plugin_id          in orac_api.plugin_services_v.plugin_id%type,
    p_service_code       in orac_api.plugin_services_v.service_code%type,
    p_owner_id           in orac_api.plugin_services_v.owner_id%type,
    p_lease_token        in orac_api.plugin_services_v.lease_token%type,
    p_state              in orac_api.plugin_services_v.current_state%type,
    p_last_error_message in orac_api.plugin_services_v.last_error_message%type default null,
    p_touch_tick         in varchar2 default 'N'
  ) return number
  is
  begin
    update orac_api.plugin_services_v
       set current_state      = p_state,
           last_error_message = p_last_error_message,
           last_tick_on       = case upper(coalesce(p_touch_tick, 'N'))
                                  when 'Y' then cast(systimestamp as timestamp)
                                  else last_tick_on
                                end
     where plugin_id = p_plugin_id
       and service_code = p_service_code
       and owner_id = p_owner_id
       and lease_token = p_lease_token;

    return sql%rowcount;
  end mark_state;
end plugin_services_tapi;
/
--rollback drop package body orac_api.plugin_services_tapi;
