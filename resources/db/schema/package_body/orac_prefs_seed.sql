create or replace package body orac.orac_prefs_seed as
-- ===================================================================
-- author      : clive bostock
-- date        : 2025-08-31
-- description : default preference seeding into orac.user_preferences.
--               stores valid json literals as text; oracle implicitly
--               converts to json data type on insert/update.
--               now also seeds/updates value_type ('string','number','boolean').
-- ===================================================================

  ------------------------------------------------------------------------------
  -- defaults_q
  -- returns one varchar per row in the form:
  --   key <TAB> value_type <TAB> json_literal
  -- examples of json_literal:
  --   '"DD-MON-YYYY HH24:MI"'  -- json string
  --   50                       -- json number
  --   true / false             -- json boolean
  ------------------------------------------------------------------------------
  function defaults_q return sys.odcivarchar2list pipelined is
    sep constant varchar2(1) := chr(9);
  begin
    pipe row('date_format'          || sep || 'string'  || sep || '"DD-MON-YYYY HH24:MI"');
    pipe row('timezone'             || sep || 'string'  || sep || '"Europe/London"');
    pipe row('theme_style'          || sep || 'string'  || sep || '"Vita"');
    pipe row('landing_page_id'      || sep || 'number'  || sep || '0');
    pipe row('rows_per_report'      || sep || 'number'  || sep || '50');

    pipe row('email_opt_in'         || sep || 'boolean' || sep || 'true');
    pipe row('push_opt_in'          || sep || 'boolean' || sep || 'false');

    pipe row('tts_voice'            || sep || 'string'  || sep || '"en-GB-female-1"');
    pipe row('tts_rate'             || sep || 'number'  || sep || '0.95');
    pipe row('tts_pitch'            || sep || 'number'  || sep || '0.0');

    -- use 0 instead of json null to satisfy USER_PREF_CK1
    pipe row('default_llm_id'       || sep || 'number'  || sep || '0');

    pipe row('temperature'          || sep || 'number'  || sep || '0.2');
    pipe row('max_tokens'           || sep || 'number'  || sep || '512');
    pipe row('strip_reasoning_tags' || sep || 'boolean' || sep || 'true');
    pipe row('show_reasoning'       || sep || 'boolean' || sep || 'false');
    pipe row('force_concise'        || sep || 'boolean' || sep || 'true');

    pipe row('enable_feedback'      || sep || 'boolean' || sep || 'true');
    pipe row('enable_advanced_mode' || sep || 'boolean' || sep || 'false');
    return;
  end defaults_q;

  ------------------------------------------------------------------------------
  -- seed_user: insert any missing prefs; optionally overwrite existing values.
  -- p_overwrite=false → only inserts missing keys
  -- p_overwrite=true  → inserts missing + updates existing with new defaults
  ------------------------------------------------------------------------------
  procedure seed_user(p_user_id in number, p_overwrite in boolean default false) is
  begin
    -- ensure the user exists
    declare
      l_dummy number;
    begin
      select 1 into l_dummy from orac.users where user_id = p_user_id;
    exception
      when no_data_found then
        raise_application_error(-20001, 'User '||p_user_id||' does not exist in ORAC.USERS');
    end;

    -- parse triples: key, value_type, json_lit
    -- pattern: ^([^\t]+)\t([^\t]+)\t(.*)$  → subexpr 1,2,3
    merge into orac.user_preferences p
    using (
      select
        regexp_substr(t.column_value,
                      '^([^' || chr(9) || ']+)' || chr(9) ||
                      '([^' || chr(9) || ']+)' || chr(9) ||
                      '(.*)$', 1, 1, null, 1) as pref_key,
        regexp_substr(t.column_value,
                      '^([^' || chr(9) || ']+)' || chr(9) ||
                      '([^' || chr(9) || ']+)' || chr(9) ||
                      '(.*)$', 1, 1, null, 2) as value_type,
        regexp_substr(t.column_value,
                      '^([^' || chr(9) || ']+)' || chr(9) ||
                      '([^' || chr(9) || ']+)' || chr(9) ||
                      '(.*)$', 1, 1, null, 3) as json_lit
      from table(defaults_q) t
    ) d
    on (p.user_id = p_user_id and p.pref_key = d.pref_key)
    when not matched then
      insert (user_id, pref_key, value_type, pref_value)
      values (p_user_id, d.pref_key, d.value_type, d.json_lit);

    if p_overwrite then
      merge into orac.user_preferences p
      using (
        select
          regexp_substr(t.column_value,
                        '^([^' || chr(9) || ']+)' || chr(9) ||
                        '([^' || chr(9) || ']+)' || chr(9) ||
                        '(.*)$', 1, 1, null, 1) as pref_key,
          regexp_substr(t.column_value,
                        '^([^' || chr(9) || ']+)' || chr(9) ||
                        '([^' || chr(9) || ']+)' || chr(9) ||
                        '(.*)$', 1, 1, null, 2) as value_type,
          regexp_substr(t.column_value,
                        '^([^' || chr(9) || ']+)' || chr(9) ||
                        '([^' || chr(9) || ']+)' || chr(9) ||
                        '(.*)$', 1, 1, null, 3) as json_lit
        from table(defaults_q) t
      ) d
      on (p.user_id = p_user_id and p.pref_key = d.pref_key)
      when matched then
        update set p.value_type = d.value_type,
                   p.pref_value = d.json_lit;
    end if;

    commit;
  end seed_user;

  ------------------------------------------------------------------------------
  -- seed_all: apply seed_user to all active users
  ------------------------------------------------------------------------------
  procedure seed_all(p_overwrite in boolean default false) is
  begin
    for r in (select user_id from orac.users where is_active = 'Y') loop
      seed_user(p_user_id => r.user_id, p_overwrite => p_overwrite);
    end loop;
  end seed_all;

end orac_prefs_seed;
/

