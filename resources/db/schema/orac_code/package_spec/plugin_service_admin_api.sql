--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_package_spec_plugin_service_admin_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-07-07
-- __description__: controlled plugin service administration API for APEX operators

create or replace package orac_code.plugin_service_admin_api as
  procedure set_policy(
    p_plugin_id    in orac_api.plugin_services_v.plugin_id%type,
    p_service_code in orac_api.plugin_services_v.service_code%type,
    p_policy       in orac_api.plugin_services_v.policy_override%type,
    p_row_version  in orac_api.plugin_services_v.row_version%type
  );
end plugin_service_admin_api;
/

--rollback drop package orac_code.plugin_service_admin_api;
