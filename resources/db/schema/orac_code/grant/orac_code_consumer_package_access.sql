-- __author__: clive
-- __date__: 2026-04-25
-- __description__: grant ORAC_CODE business packages to consumer schemas

grant execute on orac_code.orac_prefs_seed to orac_apx_pub;
grant execute on orac_code.orac_prefs_seed to orac;
grant execute on orac_code.preference_lov_api to orac_apx_pub;
grant execute on orac_code.preference_lov_api to orac;
grant execute on orac_code.user_preferences_api to orac_apx_pub;
grant execute on orac_code.user_preferences_api to orac;
