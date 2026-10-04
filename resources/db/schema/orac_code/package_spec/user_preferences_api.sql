--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_package_spec_user_preferences_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-04-26
-- __description__: ORAC_CODE wrapper API for user preference maintenance

create or replace package orac_code.user_preferences_api as
  function validate_preference_value(
    p_pref_key     in orac_api.user_preferences_v.pref_key%type,
    p_pref_value   in orac_api.user_preferences_v.pref_value%type,
    p_value_type   in orac_api.preference_definitions_v.value_type%type default null,
    p_apex_page_item_name in varchar2 default null
  ) return varchar2;

  procedure ins(
    p_pref_id      in out orac_api.user_preferences_v.pref_id%type,
    p_user_id      in     orac_api.user_preferences_v.user_id%type,
    p_pref_key     in     orac_api.user_preferences_v.pref_key%type,
    p_pref_value   in     orac_api.user_preferences_v.pref_value%type,
    p_value_type   in     orac_api.preference_definitions_v.value_type%type,
    p_row_version     out orac_api.user_preferences_v.row_version%type,
    p_apex_page_item_name in varchar2 default null
  );

  procedure upd(
    p_pref_id      in out orac_api.user_preferences_v.pref_id%type,
    p_user_id      in     orac_api.user_preferences_v.user_id%type,
    p_pref_key     in     orac_api.user_preferences_v.pref_key%type,
    p_pref_value   in     orac_api.user_preferences_v.pref_value%type,
    p_value_type   in     orac_api.preference_definitions_v.value_type%type,
    p_row_version     out orac_api.user_preferences_v.row_version%type,
    p_apex_page_item_name in varchar2 default null
  );

  procedure del(
    p_pref_id      in out orac_api.user_preferences_v.pref_id%type,
    p_row_version     out orac_api.user_preferences_v.row_version%type
  );

  function get_system_scalar(
    p_pref_key in orac_api.user_preferences_v.pref_key%type
  ) return varchar2;

  procedure set_system_scalar(
    p_pref_key   in orac_api.user_preferences_v.pref_key%type,
    p_pref_value in orac_api.user_preferences_v.pref_value%type
  );

  procedure migrate_system_scalar(
    p_pref_key     in orac_api.user_preferences_v.pref_key%type,
    p_config_value in varchar2
  );

  function get_system_general_chat_llm return number;

  procedure set_system_general_chat_llm(
    p_llm_id in number
  );

  procedure migrate_general_chat_llm(
    p_config_provider in varchar2,
    p_config_model    in varchar2
  );
end user_preferences_api;
/

--rollback drop package orac_code.user_preferences_api;
