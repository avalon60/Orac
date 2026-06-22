--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_package_spec_preference_lov_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: ORAC_CODE helper for preference-driven LOV resolution

create or replace package orac_code.preference_lov_api as
  function get_lov_json(
    p_pref_key      in orac_api.preference_definitions_v.pref_key%type,
    p_search        in varchar2 default null,
    p_current_value in varchar2 default null,
    p_limit         in pls_integer default 50
  ) return clob;
end preference_lov_api;
/

--rollback drop package orac_code.preference_lov_api;
