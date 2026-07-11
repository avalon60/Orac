--liquibase formatted sql

--changeset clive:create_package_body_orac_code_package_body_plugin_service_admin_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-07-07
-- __description__: controlled plugin service administration API body for APEX operators

create or replace package body orac_code.plugin_service_admin_api as
  procedure require_admin
  is
  begin
    if orac_code.plugin_apex_app_auth_api.has_required_role('ORAC_ADMIN') <> 1
    then
      raise_application_error(
        -20210,
        'Only ORAC_ADMIN users can change plugin service policy.'
      );
    end if;
  end require_admin;

  procedure set_policy(
    p_plugin_id    in orac_api.plugin_services_v.plugin_id%type,
    p_service_code in orac_api.plugin_services_v.service_code%type,
    p_policy       in orac_api.plugin_services_v.policy_override%type,
    p_row_version  in orac_api.plugin_services_v.row_version%type
  )
  is
  begin
    require_admin;

    orac_code.plugin_service_api.set_service_policy(
      p_plugin_id    => p_plugin_id,
      p_service_code => p_service_code,
      p_policy       => p_policy,
      p_row_version  => p_row_version
    );
  exception
    when others then
      if sqlcode = -20202
      then
        raise_application_error(
          -20202,
          'Plugin service was changed by another session. Refresh and try again.'
        );
      end if;

      raise;
  end set_policy;
end plugin_service_admin_api;
/

--rollback drop package body orac_code.plugin_service_admin_api;
