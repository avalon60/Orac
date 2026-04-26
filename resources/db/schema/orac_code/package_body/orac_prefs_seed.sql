-- __author__: clive
-- __date__: 2026-04-25
-- __description__: seed default user preferences through ORAC_API views and TAPIs

create or replace package body orac_code.orac_prefs_seed as

  function defaults_q return sys.odcivarchar2list pipelined is
    l_sep constant varchar2(1) := chr(9);
  begin
    pipe row('date_format'          || l_sep || 'string'  || l_sep || '"DD-MON-YYYY HH24:MI"');
    pipe row('timezone'             || l_sep || 'string'  || l_sep || '"Europe/London"');
    pipe row('theme_style'          || l_sep || 'string'  || l_sep || '"Vita"');
    pipe row('landing_page_id'      || l_sep || 'number'  || l_sep || '0');
    pipe row('rows_per_report'      || l_sep || 'number'  || l_sep || '50');
    pipe row('email_opt_in'         || l_sep || 'boolean' || l_sep || 'true');
    pipe row('push_opt_in'          || l_sep || 'boolean' || l_sep || 'false');
    pipe row('tts_voice'            || l_sep || 'string'  || l_sep || '"en-GB-female-1"');
    pipe row('tts_rate'             || l_sep || 'number'  || l_sep || '0.95');
    pipe row('tts_pitch'            || l_sep || 'number'  || l_sep || '0.0');
    pipe row('default_llm_id'       || l_sep || 'number'  || l_sep || '0');
    pipe row('temperature'          || l_sep || 'number'  || l_sep || '0.2');
    pipe row('max_tokens'           || l_sep || 'number'  || l_sep || '512');
    pipe row('strip_reasoning_tags' || l_sep || 'boolean' || l_sep || 'true');
    pipe row('show_reasoning'       || l_sep || 'boolean' || l_sep || 'false');
    pipe row('force_concise'        || l_sep || 'boolean' || l_sep || 'true');
    pipe row('enable_feedback'      || l_sep || 'boolean' || l_sep || 'true');
    pipe row('enable_advanced_mode' || l_sep || 'boolean' || l_sep || 'false');
    return;
  end defaults_q;

  procedure seed_user(
    p_user_id   in number,
    p_overwrite in boolean default false
  ) is
    l_pref_id      orac_api.user_preferences_v.pref_id%type;
    l_pref_key     orac_api.user_preferences_v.pref_key%type;
    l_value_type   orac_api.user_preferences_v.value_type%type;
    l_pref_value   orac_api.user_preferences_v.pref_value%type;
    l_row_version  orac_api.user_preferences_v.row_version%type;
    l_user_exists  number;
    l_sep          constant varchar2(1) := chr(9);
  begin
    select count(*)
      into l_user_exists
      from orac_api.users
     where user_id = p_user_id;

    if l_user_exists = 0 then
      raise_application_error(-20001, 'User ' || p_user_id || ' does not exist in ORAC_API.USERS');
    end if;

    for rec in (
      select regexp_substr(t.column_value, '^([^' || l_sep || ']+)', 1, 1, null, 1) as pref_key,
             regexp_substr(t.column_value, '^([^' || l_sep || ']+)' || l_sep || '([^' || l_sep || ']+)', 1, 1, null, 2) as value_type,
             regexp_substr(t.column_value, '^([^' || l_sep || ']+)' || l_sep || '([^' || l_sep || ']+)' || l_sep || '(.*)$', 1, 1, null, 3) as pref_value
        from table(defaults_q) t
    ) loop
      begin
        select pref_id, row_version
          into l_pref_id, l_row_version
          from orac_api.user_preferences_v
         where user_id = p_user_id
           and pref_key = rec.pref_key;

        if p_overwrite then
          orac_api.user_preferences_tapi.upd(
            p_pref_id     => l_pref_id,
            p_user_id     => p_user_id,
            p_pref_key    => rec.pref_key,
            p_pref_value  => rec.pref_value,
            p_value_type  => rec.value_type,
            p_row_version => l_row_version
          );
        end if;
      exception
        when no_data_found then
          l_pref_id := null;
          orac_api.user_preferences_tapi.ins(
            p_pref_id     => l_pref_id,
            p_user_id     => p_user_id,
            p_pref_key    => rec.pref_key,
            p_pref_value  => rec.pref_value,
            p_value_type  => rec.value_type,
            p_row_version => l_row_version
          );
      end;
    end loop;
  end seed_user;

  procedure seed_all(
    p_overwrite in boolean default false
  ) is
  begin
    for rec in (
      select user_id
        from orac_api.users
       where is_active = 'Y'
    ) loop
      seed_user(
        p_user_id   => rec.user_id,
        p_overwrite => p_overwrite
      );
    end loop;
  end seed_all;

end orac_prefs_seed;
/
