--liquibase formatted sql

--changeset clive:create_package_body_orac_code_package_body_plugin_service_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: implements Orac-owned plugin service policy, status, and lease API

create or replace package body orac_code.plugin_service_api as
  procedure assert_policy(
    p_policy in varchar2,
    p_name   in varchar2
  )
  is
  begin
    if p_policy not in ('disabled', 'manual', 'auto')
    then
      raise_application_error(-20200, p_name || ' must be disabled, manual, or auto.');
    end if;
  end assert_policy;

  procedure assert_state(
    p_state in varchar2
  )
  is
  begin
    if p_state not in (
         'registered',
         'starting',
         'running',
         'stopping',
         'stopped',
         'failed',
         'disabled',
         'lease_lost'
       )
    then
      raise_application_error(-20201, 'Plugin service state is invalid.');
    end if;
  end assert_state;

  procedure register_service(
    p_plugin_id       in orac_api.plugin_services_v.plugin_id%type,
    p_service_code    in orac_api.plugin_services_v.service_code%type,
    p_service_name    in orac_api.plugin_services_v.service_name%type,
    p_entry_point     in orac_api.plugin_services_v.entry_point%type,
    p_execution_model in orac_api.plugin_services_v.execution_model%type,
    p_manifest_policy in orac_api.plugin_services_v.manifest_policy%type
  )
  is
    l_row orac_api.plugin_services_v%rowtype;
    l_effective_policy orac_api.plugin_services_v.manifest_policy%type;
  begin
    assert_policy(p_manifest_policy, 'Manifest policy');

    begin
      orac_api.plugin_services_tapi.get_by_key(
        p_plugin_id    => p_plugin_id,
        p_service_code => p_service_code,
        p_row          => l_row
      );
      l_row.service_name := p_service_name;
      l_row.entry_point := p_entry_point;
      l_row.execution_model := p_execution_model;
      l_row.manifest_policy := p_manifest_policy;
      l_effective_policy := coalesce(l_row.policy_override, p_manifest_policy);
      if l_effective_policy = 'disabled'
      then
        l_row.current_state := 'disabled';
      elsif l_row.current_state = 'disabled'
      then
        l_row.current_state := 'registered';
      end if;
      orac_api.plugin_services_tapi.upd(l_row.plugin_service_id, l_row);
    exception
      when no_data_found then
        l_row.plugin_id := p_plugin_id;
        l_row.service_code := p_service_code;
        l_row.service_name := p_service_name;
        l_row.entry_point := p_entry_point;
        l_row.execution_model := p_execution_model;
        l_row.manifest_policy := p_manifest_policy;
        l_row.current_state := case p_manifest_policy
                                 when 'disabled' then 'disabled'
                                 else 'registered'
                               end;
        orac_api.plugin_services_tapi.ins(l_row);
    end;
  end register_service;

  procedure set_service_policy(
    p_plugin_id    in orac_api.plugin_services_v.plugin_id%type,
    p_service_code in orac_api.plugin_services_v.service_code%type,
    p_policy       in orac_api.plugin_services_v.policy_override%type,
    p_row_version  in orac_api.plugin_services_v.row_version%type
  )
  is
    l_row orac_api.plugin_services_v%rowtype;
  begin
    assert_policy(p_policy, 'Service policy');
    orac_api.plugin_services_tapi.get_by_key(
      p_plugin_id    => p_plugin_id,
      p_service_code => p_service_code,
      p_row          => l_row
    );

    if l_row.row_version <> p_row_version
    then
      raise_application_error(-20202, 'Plugin service was changed by another session.');
    end if;

    l_row.policy_override := p_policy;
    if p_policy = 'disabled'
    then
      l_row.current_state := 'disabled';
      l_row.owner_id := null;
      l_row.lease_token := null;
      l_row.lease_expires_on := null;
    elsif l_row.current_state = 'disabled'
    then
      l_row.current_state := 'registered';
    end if;

    orac_api.plugin_services_tapi.upd(l_row.plugin_service_id, l_row);
  end set_service_policy;

  function try_acquire_service_lease(
    p_plugin_id     in orac_api.plugin_services_v.plugin_id%type,
    p_service_code  in orac_api.plugin_services_v.service_code%type,
    p_owner_id      in orac_api.plugin_services_v.owner_id%type,
    p_lease_seconds in number
  ) return varchar2
  is
    l_lease_token orac_api.plugin_services_v.lease_token%type;
  begin
    if p_lease_seconds is null or p_lease_seconds < 1
    then
      raise_application_error(-20203, 'Lease seconds must be at least 1.');
    end if;

    orac_api.plugin_services_tapi.try_acquire_lease(
      p_plugin_id     => p_plugin_id,
      p_service_code  => p_service_code,
      p_owner_id      => p_owner_id,
      p_lease_seconds => p_lease_seconds,
      p_lease_token   => l_lease_token
    );
    return l_lease_token;
  end try_acquire_service_lease;

  function heartbeat_service_lease(
    p_plugin_id     in orac_api.plugin_services_v.plugin_id%type,
    p_service_code  in orac_api.plugin_services_v.service_code%type,
    p_owner_id      in orac_api.plugin_services_v.owner_id%type,
    p_lease_token   in orac_api.plugin_services_v.lease_token%type,
    p_lease_seconds in number
  ) return number
  is
  begin
    if p_lease_seconds is null or p_lease_seconds < 1
    then
      raise_application_error(-20203, 'Lease seconds must be at least 1.');
    end if;

    return orac_api.plugin_services_tapi.heartbeat_lease(
      p_plugin_id     => p_plugin_id,
      p_service_code  => p_service_code,
      p_owner_id      => p_owner_id,
      p_lease_token   => p_lease_token,
      p_lease_seconds => p_lease_seconds
    );
  end heartbeat_service_lease;

  function release_service_lease(
    p_plugin_id    in orac_api.plugin_services_v.plugin_id%type,
    p_service_code in orac_api.plugin_services_v.service_code%type,
    p_owner_id     in orac_api.plugin_services_v.owner_id%type,
    p_lease_token  in orac_api.plugin_services_v.lease_token%type
  ) return number
  is
  begin
    return orac_api.plugin_services_tapi.release_lease(
      p_plugin_id    => p_plugin_id,
      p_service_code => p_service_code,
      p_owner_id     => p_owner_id,
      p_lease_token  => p_lease_token
    );
  end release_service_lease;

  function mark_service_state(
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
    assert_state(p_state);
    return orac_api.plugin_services_tapi.mark_state(
      p_plugin_id          => p_plugin_id,
      p_service_code       => p_service_code,
      p_owner_id           => p_owner_id,
      p_lease_token        => p_lease_token,
      p_state              => p_state,
      p_last_error_message => substr(p_last_error_message, 1, 2000),
      p_touch_tick         => p_touch_tick
    );
  end mark_service_state;
end plugin_service_api;
/
--rollback drop package body orac_code.plugin_service_api;
