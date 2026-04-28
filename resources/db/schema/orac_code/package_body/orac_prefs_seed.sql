-- __author__: clive
-- __date__: 2026-04-25
-- __description__: seed default user preferences through ORAC_API views and TAPIs

create or replace package body orac_code.orac_prefs_seed as

  function defaults_q return sys.odcivarchar2list pipelined is
    l_sep constant varchar2(1) := chr(9);
  begin
    for rec in (
      select pref_key,
             value_type,
             json_serialize(default_value returning clob) as pref_value
        from orac_api.preference_definitions_v
       where is_active = 'Y'
         and default_value is not null
         and json_serialize(default_value returning varchar2(4000)) <> 'null'
       order by display_sequence, pref_key
    ) loop
      pipe row(rec.pref_key || l_sep || rec.value_type || l_sep || rec.pref_value);
    end loop;

    return;
  end defaults_q;

  procedure seed_user(
    p_user_id   in number,
    p_overwrite in boolean default false
  ) is
    l_pref_id      orac_api.user_preferences_v.pref_id%type;
    l_pref_value   orac_api.user_preferences_v.pref_value%type;
    l_row_version  orac_api.user_preferences_v.row_version%type;
    l_user_exists  number;
  begin
    select count(*)
      into l_user_exists
      from orac_api.users
     where user_id = p_user_id;

    if l_user_exists = 0 then
      raise_application_error(-20001, 'User ' || p_user_id || ' does not exist in ORAC_API.USERS');
    end if;

    for rec in (
      select pref_key,
             value_type,
             json_serialize(default_value returning clob) as pref_value
       from orac_api.preference_definitions_v
       where is_active = 'Y'
         and default_value is not null
         and json_serialize(default_value returning varchar2(4000)) <> 'null'
       order by display_sequence, pref_key
    ) loop
      begin
        select pref_id, row_version
          into l_pref_id, l_row_version
          from orac_api.user_preferences_v
         where user_id = p_user_id
           and pref_key = rec.pref_key;

        if p_overwrite then
          l_pref_value := json(rec.pref_value);
          orac_api.user_preferences_tapi.upd(
            p_pref_id     => l_pref_id,
            p_user_id     => p_user_id,
            p_pref_key    => rec.pref_key,
            p_pref_value  => l_pref_value,
            p_value_type  => rec.value_type,
            p_row_version => l_row_version
          );
        end if;
      exception
        when no_data_found then
          l_pref_id := null;
          l_pref_value := json(rec.pref_value);
          orac_api.user_preferences_tapi.ins(
            p_pref_id     => l_pref_id,
            p_user_id     => p_user_id,
            p_pref_key    => rec.pref_key,
            p_pref_value  => l_pref_value,
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
