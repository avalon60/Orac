create or replace package body orac_utils
as
  function header(p_name in varchar2) return varchar2
  is
  begin
    return owa_util.get_cgi_env('HTTP_' || replace(upper(p_name), '-', '_'));
  end;

  function b64url_to_raw(p_b64url in varchar2) return raw
  is
    l_b64 varchar2(32767) := replace(replace(p_b64url, '-', '+'), '_', '/');
    l_pad pls_integer := mod(4 - mod(length(l_b64), 4), 4);
  begin
    if l_pad > 0 then
      l_b64 := l_b64 || rpad('=', l_pad, '=');
    end if;
    return utl_encode.base64_decode(utl_raw.cast_to_raw(l_b64));
  end;

  function hmac_sha256(p_secret_raw in raw, p_message in varchar2) return raw
  is
  begin
    return dbms_crypto.mac(
      src => utl_raw.cast_to_raw(p_message),
      typ => dbms_crypto.hmac_sh256,
      key => p_secret_raw
    );
  end;

  function get_setting(p_key in varchar2) return varchar2
  is
    l_val orac.auth_settings.setting_value%type;
  begin
    select setting_value
      into l_val
      from orac.auth_settings
     where setting_key = p_key;

    return l_val;
  exception
    when no_data_found then
      return null;
  end;

  function fresh_timestamp(p_iso_utc in varchar2, p_skew_seconds in pls_integer default 120) return boolean
  is
    l_ts_utc   timestamp with time zone;
    l_now_utc  timestamp with time zone := systimestamp at time zone 'UTC';
  begin
    l_ts_utc := to_timestamp_tz(p_iso_utc, 'yyyy-mm-dd"T"hh24:mi:ss"Z"');
    if abs(extract(second from (l_now_utc - l_ts_utc))
         + 60*extract(minute from (l_now_utc - l_ts_utc))
         + 3600*extract(hour from (l_now_utc - l_ts_utc))
         + 86400*extract(day from (l_now_utc - l_ts_utc))) <= p_skew_seconds
    then
      return true;
    end if;
    return false;
  exception
    when others then
      return false;
  end;

  function nonce_unused(p_nonce in varchar2, p_ttl_seconds in pls_integer default 600) return boolean
  is
    l_cnt integer;
  begin
    select count(*)
      into l_cnt
      from orac.auth_nonces
     where nonce = p_nonce
       and created_on > systimestamp - numtodsinterval(p_ttl_seconds, 'second');

    return l_cnt = 0;
  end;

  procedure mark_nonce_used(p_nonce in varchar2)
  is
  begin
    insert into orac.auth_nonces (nonce) values (p_nonce);
    commit;
  exception
    when dup_val_on_index then null;
  end;

  function resolve_user(p_os_user in varchar2) return varchar2
  is
    l_user_id orac.user_synonyms.user_id%type;
  begin
    select user_id
      into l_user_id
      from orac.user_synonyms
     where alias_type = 'os'
       and alias_value = p_os_user
       and is_active = 1;

    return l_user_id;
  exception
    when no_data_found then
      return null;
  end;

  function device_allowed(p_device_id in varchar2, p_user_id in varchar2) return boolean
  is
    l_dummy number;
  begin
    select 1
      into l_dummy
      from orac.devices
     where device_id = p_device_id
       and user_id   = p_user_id
       and is_active = 1;

    return true;
  exception
    when no_data_found then
      return false;
  end;

  procedure set_session_identity(p_user_id in varchar2, p_host in varchar2, p_device in varchar2)
  is
  begin
    dbms_session.set_identifier(p_user_id);
    dbms_application_info.set_client_info(substr(nvl(p_host,'?')||'|'||nvl(p_device,'?'), 1, 64));
  end;

  procedure slave_precheck(p_require_sig in boolean default true)
  is
    l_os_user   varchar2(256) := header('X-Zen-User');
    l_devid     varchar2(256) := nvl(header('X-Zen-Devid'), header('X-Zen-Mac'));
    l_host      varchar2(256) := header('X-Zen-Host');
    l_user_id   varchar2(64);
  begin
    l_user_id := resolve_user(l_os_user);

    if l_user_id is null then
      owa_util.status_line(403, 'forbidden');
      htp.p('unknown user');
      return;
    end if;

    if not device_allowed(l_devid, l_user_id) then
      owa_util.status_line(403, 'forbidden');
      htp.p('device not allowed');
      return;
    end if;

    set_session_identity(l_user_id, l_host, l_devid);
  end;
end orac_utils;
/

