-- __author__: clive
-- __date__: 2026-04-27
-- __description__: ORAC_CODE helper for preference-driven LOV resolution

create or replace package orac_code.preference_lov_api as
  function get_lov_json(
    p_pref_key      in orac_api.preference_definitions_v.pref_key%type,
    p_search        in varchar2 default null,
    p_current_value in varchar2 default null
  ) return clob;
end preference_lov_api;
/
