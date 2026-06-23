--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_package_spec_plugin_apex_app_auth_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-22
-- __description__: plugin APEX application authorization helper API

create or replace package orac_code.plugin_apex_app_auth_api as
  function has_required_role(
    p_required_role in varchar2,
    p_app_user      in varchar2 default null
  ) return number;
end plugin_apex_app_auth_api;
/

--rollback drop package orac_code.plugin_apex_app_auth_api;
