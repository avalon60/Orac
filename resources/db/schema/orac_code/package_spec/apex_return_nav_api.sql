--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_package_spec_apex_return_nav_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-07-07
-- __description__: validated cross-application APEX return navigation API

create or replace package orac_code.apex_return_nav_api as
  c_max_depth constant pls_integer := 5;

  function normalize_stack(
    p_stack in varchar2 default null
  ) return varchar2;

  function launch_url(
    p_target_app_id  in number,
    p_target_page_id in number,
    p_request        in varchar2 default null,
    p_clear_cache    in varchar2 default null
  ) return varchar2;

  function return_depth(
    p_stack in varchar2 default null
  ) return number;

  function return_label(
    p_position in pls_integer,
    p_stack    in varchar2 default null
  ) return varchar2;

  function return_url(
    p_position in pls_integer,
    p_stack    in varchar2 default null
  ) return varchar2;
end apex_return_nav_api;
/

--rollback drop package orac_code.apex_return_nav_api;
