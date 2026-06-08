-- __author__: clive
-- __date__: 2026-04-25
-- __description__: grant ORAC_CODE reporting and business views to consumer schemas

grant select on orac_code.messages_per_day_v to orac_apx_pub;
grant select on orac_code.llm_usage_breakdown_v to orac_apx_pub;
grant select on orac_code.llm_registry_probe_v to orac_apx_pub;
grant select on orac_code.token_usage_trend_v to orac_apx_pub;
grant select on orac_code.message_role_breakdown_v to orac_apx_pub;
grant select, insert, update, delete on orac_code.user_preferences_v to orac_apx_pub;
grant read on orac_code.user_preferences_v to orac_apx_pub;
grant select on orac_code.user_preferences_display_v to orac_apx_pub;

grant select on orac_code.messages_per_day_v to orac;
grant select on orac_code.llm_usage_breakdown_v to orac;
grant select on orac_code.llm_registry_probe_v to orac;
grant select on orac_code.token_usage_trend_v to orac;
grant select on orac_code.message_role_breakdown_v to orac;
grant select, insert, update, delete on orac_code.user_preferences_v to orac;
grant read on orac_code.user_preferences_v to orac;
grant select on orac_code.user_preferences_display_v to orac;
grant read on orac_code.plugin_registry_v to orac;
