-- __author__: clive
-- __date__: 2026-04-26
-- __description__: ORAC_CODE wrapper API for user preference maintenance

create or replace package orac_code.user_preferences_api as
  procedure ins(
    p_pref_id      in out orac_api.user_preferences_v.pref_id%type,
    p_user_id      in     orac_api.user_preferences_v.user_id%type,
    p_pref_key     in     orac_api.user_preferences_v.pref_key%type,
    p_pref_value   in     orac_api.user_preferences_v.pref_value%type,
    p_value_type   in     orac_api.user_preferences_v.value_type%type,
    p_row_version     out orac_api.user_preferences_v.row_version%type
  );

  procedure upd(
    p_pref_id      in out orac_api.user_preferences_v.pref_id%type,
    p_user_id      in     orac_api.user_preferences_v.user_id%type,
    p_pref_key     in     orac_api.user_preferences_v.pref_key%type,
    p_pref_value   in     orac_api.user_preferences_v.pref_value%type,
    p_value_type   in     orac_api.user_preferences_v.value_type%type,
    p_row_version     out orac_api.user_preferences_v.row_version%type
  );

  procedure del(
    p_pref_id      in out orac_api.user_preferences_v.pref_id%type,
    p_row_version     out orac_api.user_preferences_v.row_version%type
  );
end user_preferences_api;
/
