--liquibase formatted sql

--changeset clive:create_package_body_orac_code_installation_bootstrap_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-10-03
-- __description__: provision reserved and installer-derived Orac principals

create or replace package body orac_code.installation_bootstrap_api as

  function normalise_username(
    p_username in varchar2
  ) return varchar2
  is
    l_username orac_api.users_v.username%type;
  begin
    l_username := lower(trim(p_username));
    if length(l_username) not between 3 and 32
       or not regexp_like(l_username, '^[a-z][a-z0-9]*([._-][a-z0-9]+)*$')
    then
      raise_application_error(
        -20070,
        'Installer username must be 3-32 lowercase-compatible characters and start with a letter.'
      );
    end if;
    return l_username;
  end normalise_username;

  function create_user(
    p_username     in orac_api.users_v.username%type,
    p_display_name in orac_api.users_v.display_name%type,
    p_is_active    in orac_api.users_v.is_active%type
  ) return number
  is
    l_row orac_api.users_v%rowtype;
  begin
    l_row.username := p_username;
    l_row.display_name := p_display_name;
    l_row.is_active := p_is_active;
    orac_api.users_tapi.ins(p_row => l_row);
    return l_row.user_id;
  end create_user;

  procedure ensure_system_principal is
    l_system_id orac_api.users_v.user_id%type;
    l_system_count number;
    l_pref_id   orac_api.user_preferences_v.pref_id%type;
    l_row_ver   orac_api.user_preferences_v.row_version%type;
  begin
    select max(
             case
               when username = gc_system_username and is_active = 'N'
               then user_id
             end
           ),
           count(*)
      into l_system_id,
           l_system_count
      from orac_api.users_v
     where lower(username) = gc_system_username;

    if l_system_count = 0
    then
      l_system_id := create_user(
        gc_system_username,
        gc_system_username,
        'N'
      );
    elsif l_system_count <> 1 or l_system_id is null
    then
      raise_application_error(
        -20071,
        'Reserved SYSTEM principal has an incompatible interactive identity.'
      );
    end if;

    begin
      select pref_id
        into l_pref_id
        from orac_api.user_preferences_v
       where user_id = l_system_id
         and pref_key = 'general_chat_llm';
    exception
      when no_data_found then
        l_pref_id := null;
        orac_api.user_preferences_tapi.ins(
          p_pref_id     => l_pref_id,
          p_user_id     => l_system_id,
          p_pref_key    => 'general_chat_llm',
          p_pref_value  => json('0'),
          p_row_version => l_row_ver
        );
    end;
  end ensure_system_principal;

  procedure ensure_principals(
    p_installer_username in varchar2,
    p_user_created       out varchar2
  ) is
    l_username orac_api.users_v.username%type;
    l_user_id  orac_api.users_v.user_id%type;
  begin
    ensure_system_principal;
    l_username := normalise_username(p_installer_username);

    if l_username in (gc_system_username, 'orac_admin')
    then
      raise_application_error(
        -20072,
        'Installer username is reserved: ' || l_username
      );
    end if;

    begin
      select user_id
        into l_user_id
        from orac_api.users_v
       where lower(username) = l_username;
      p_user_created := 'N';
    exception
      when no_data_found then
        l_user_id := create_user(
          l_username,
          initcap(l_username),
          'Y'
        );
        orac_code.orac_prefs_seed.seed_user(
          p_user_id   => l_user_id,
          p_overwrite => false
        );
        p_user_created := 'Y';
    end;
  end ensure_principals;

end installation_bootstrap_api;
/

--rollback drop package body orac_code.installation_bootstrap_api;
