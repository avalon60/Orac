--liquibase formatted sql

--changeset clive:create_package_body_orac_code_package_body_preference_lov_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-04-29
-- __description__: ORAC_CODE helper for preference-driven LOV resolution

create or replace package body orac_code.preference_lov_api as
  gc_default_app_id constant number := 1042;
  gc_open_meteo_geocoder_url constant varchar2(200) := 'https://geocoding-api.open-meteo.com/v1/search';

  subtype t_pref_key is orac_api.preference_definitions_v.pref_key%type;
  subtype t_lov_type is orac_api.preference_definitions_v.lov_type%type;
  subtype t_static_lov_code is orac_api.preference_definitions_v.static_lov_code%type;
  subtype t_lov_query is orac_api.preference_definitions_v.lov_query%type;
  subtype t_is_active is orac_api.preference_definitions_v.is_active%type;

  type t_pref_definition is record (
    pref_key         t_pref_key,
    lov_type         t_lov_type,
    lov_query        t_lov_query,
    static_lov_code  t_static_lov_code,
    is_active        t_is_active
  );

  function current_app_id return number is
    l_app_id_txt varchar2(100);
  begin
    l_app_id_txt := nullif(sys_context('APEX$SESSION', 'APP_ID'), '');

    if l_app_id_txt is not null and regexp_like(l_app_id_txt, '^\d+$') then
      return to_number(l_app_id_txt);
    end if;

    return gc_default_app_id;
  end current_app_id;

  procedure append_row(
    p_rows          in out nocopy json_array_t,
    p_display_value in varchar2,
    p_return_value  in varchar2
  ) is
    l_row json_object_t := json_object_t();
  begin
    l_row.put('display_value', p_display_value);
    l_row.put('return_value', p_return_value);
    p_rows.append(l_row);
  end append_row;

  procedure load_preference_definition(
    p_pref_key         in t_pref_key,
    p_pref_definition out nocopy t_pref_definition
  ) is
  begin
    select lower(pref_key),
           lower(lov_type),
           lov_query,
           upper(static_lov_code),
           is_active
      into p_pref_definition.pref_key,
           p_pref_definition.lov_type,
           p_pref_definition.lov_query,
           p_pref_definition.static_lov_code,
           p_pref_definition.is_active
      from orac_api.preference_definitions_v
     where lower(pref_key) = lower(trim(p_pref_key));
  exception
    when no_data_found then
      p_pref_definition.pref_key := lower(trim(p_pref_key));
      p_pref_definition.lov_type := null;
      p_pref_definition.lov_query := null;
      p_pref_definition.static_lov_code := null;
      p_pref_definition.is_active := 'N';
  end load_preference_definition;

  function build_location_label(
    p_name    in varchar2,
    p_admin1  in varchar2,
    p_country in varchar2
  ) return varchar2 is
    l_label varchar2(4000);
  begin
    l_label := p_name;

    if p_admin1 is not null then
      l_label := l_label || ', ' || p_admin1;
    end if;

    if p_country is not null then
      l_label := l_label || ', ' || p_country;
    end if;

    return l_label;
  end build_location_label;

  function http_get(
    p_url in varchar2
  ) return clob is
    l_req   utl_http.req;
    l_resp  utl_http.resp;
    l_chunk varchar2(32767);
    l_body  clob;
  begin
    dbms_lob.createtemporary(l_body, true);

    l_req := utl_http.begin_request(p_url, 'GET');
    l_resp := utl_http.get_response(l_req);

    begin
      loop
        utl_http.read_text(l_resp, l_chunk, 32767);
        dbms_lob.writeappend(l_body, length(l_chunk), l_chunk);
      end loop;
    exception
      when utl_http.end_of_body then
        null;
    end;

    utl_http.end_response(l_resp);
    return l_body;
  exception
    when others then
      begin
        utl_http.end_response(l_resp);
      exception
        when others then
          null;
      end;
      if dbms_lob.istemporary(l_body) = 1 then
        dbms_lob.freetemporary(l_body);
      end if;
      raise;
  end http_get;

  procedure append_location_row(
    p_rows      in out nocopy json_array_t,
    p_name      in varchar2,
    p_latitude  in number,
    p_longitude in number,
    p_timezone  in varchar2,
    p_country   in varchar2,
    p_admin1    in varchar2
  ) is
    l_value json_object_t := json_object_t();
  begin
    if p_name is null then
      return;
    end if;

    l_value.put('name', p_name);
    l_value.put('latitude', p_latitude);
    l_value.put('longitude', p_longitude);
    l_value.put('timezone', p_timezone);

    if p_country is not null then
      l_value.put('country', p_country);
    end if;

    if p_admin1 is not null then
      l_value.put('admin1', p_admin1);
    end if;

    append_row(
      p_rows          => p_rows,
      p_display_value => build_location_label(
                           p_name    => p_name,
                           p_admin1  => p_admin1,
                           p_country => p_country
                         ),
      p_return_value  => l_value.to_clob
    );
  end append_location_row;

  procedure append_current_weather_location(
    p_rows          in out nocopy json_array_t,
    p_current_value in varchar2
  ) is
  begin
    if p_current_value is null or trim(p_current_value) is null then
      return;
    end if;

    if lower(trim(p_current_value)) = 'null' then
      return;
    end if;

    for rec in (
      select jt.name,
             jt.latitude,
             jt.longitude,
             jt.timezone,
             jt.country,
             jt.admin1
        from json_table(
               p_current_value,
               '$'
               columns (
                 name varchar2(255) path '$.name',
                 latitude number path '$.latitude',
                 longitude number path '$.longitude',
                 timezone varchar2(255) path '$.timezone',
                 country varchar2(255) path '$.country',
                 admin1 varchar2(255) path '$.admin1'
               )
             ) jt
    ) loop
      append_location_row(
        p_rows      => p_rows,
        p_name      => rec.name,
        p_latitude  => rec.latitude,
        p_longitude => rec.longitude,
        p_timezone  => rec.timezone,
        p_country   => rec.country,
        p_admin1    => rec.admin1
      );
    end loop;
  exception
    when others then
      null;
  end append_current_weather_location;

  procedure validate_sql_lov_query(
    p_pref_key   in t_pref_key,
    p_lov_query  in t_lov_query
  ) is
    l_lov_query varchar2(32767) := trim(p_lov_query);
  begin
    if l_lov_query is null then
      raise_application_error(
        -20000,
        'Preference LOV query is required for pref_key=' || p_pref_key
      );
    end if;

    if not regexp_like(l_lov_query, '^select([[:space:]]|$)', 'in') then
      raise_application_error(
        -20000,
        'Preference LOV query must be a select for pref_key=' || p_pref_key
      );
    end if;

    if regexp_like(l_lov_query, '(^|[^:[:alnum:]_])(insert|update|delete|merge|alter|drop|truncate|create|grant|revoke|commit|rollback|execute|begin|declare)([^[:alnum:]_]|$)', 'in') then
      raise_application_error(
        -20000,
        'Preference LOV query contains a prohibited keyword for pref_key=' || p_pref_key
      );
    end if;

    if instr(l_lov_query, ';') > 0 then
      raise_application_error(
        -20000,
        'Preference LOV query must not contain a semicolon for pref_key=' || p_pref_key
      );
    end if;

    if regexp_like(l_lov_query, '(^|[^[:alnum:]_])preference_lov_api[[:space:]]*\.[[:space:]]*get_lov_json([^[:alnum:]_]|$)', 'in') then
      raise_application_error(
        -20000,
        'Preference LOV query must not recurse into preference_lov_api for pref_key=' || p_pref_key
      );
    end if;
  end validate_sql_lov_query;

  procedure append_static_lov_rows(
    p_rows             in out nocopy json_array_t,
    p_static_lov_code  in t_static_lov_code
  ) is
  begin
    case upper(trim(p_static_lov_code))
      when 'DATE_FORMAT' then
        append_row(p_rows, 'DD-MON-YYYY HH24:MI', 'DD-MON-YYYY HH24:MI');
        append_row(p_rows, 'YYYY-MM-DD HH24:MI', 'YYYY-MM-DD HH24:MI');
        append_row(p_rows, 'DD/MM/YYYY HH24:MI', 'DD/MM/YYYY HH24:MI');
        append_row(p_rows, 'DD Mon YYYY HH24:MI', 'DD Mon YYYY HH24:MI');
      when 'TTS_VOICE' then
        append_row(p_rows, 'English (UK) Female 1', 'en-GB-female-1');
        append_row(p_rows, 'English (UK) Male 1', 'en-GB-male-1');
        append_row(p_rows, 'English (US) Female 1', 'en-US-female-1');
        append_row(p_rows, 'English (US) Male 1', 'en-US-male-1');
      else
        raise_application_error(
          -20000,
          'Unsupported static LOV code for pref_key lookup: ' || p_static_lov_code
        );
    end case;
  end append_static_lov_rows;

  procedure append_dynamic_lov_rows(
    p_rows          in out nocopy json_array_t,
    p_pref_key      in t_pref_key,
    p_lov_query     in t_lov_query,
    p_app_id        in number,
    p_search        in varchar2,
    p_current_value in varchar2,
    p_limit         in pls_integer
  ) is
    l_cursor      integer := dbms_sql.open_cursor;
    l_status      integer;
    l_column_cnt  pls_integer;
    l_desc_tab    dbms_sql.desc_tab2;
    l_display     varchar2(4000);
    l_return      varchar2(4000);
    procedure bind_if_present(
      p_bind_name in varchar2,
      p_value     in varchar2
    ) is
    begin
      if instr(upper(p_lov_query), ':' || upper(p_bind_name)) > 0 then
        dbms_sql.bind_variable(l_cursor, p_bind_name, p_value);
      end if;
    end bind_if_present;

    procedure bind_number_if_present(
      p_bind_name in varchar2,
      p_value     in number
    ) is
    begin
      if instr(upper(p_lov_query), ':' || upper(p_bind_name)) > 0 then
        dbms_sql.bind_variable(l_cursor, p_bind_name, p_value);
      end if;
    end bind_number_if_present;
  begin
    validate_sql_lov_query(
      p_pref_key  => p_pref_key,
      p_lov_query => p_lov_query
    );

    dbms_sql.parse(l_cursor, p_lov_query, dbms_sql.native);
    bind_number_if_present('APP_ID', p_app_id);
    bind_if_present('APEX$SEARCH', p_search);
    bind_if_present('P_SEARCH', p_search);
    bind_if_present('CURRENT_VALUE', p_current_value);
    bind_if_present('P_CURRENT_VALUE', p_current_value);
    bind_if_present('PREF_KEY', p_pref_key);
    bind_number_if_present('P_LIMIT', p_limit);

    dbms_sql.describe_columns2(l_cursor, l_column_cnt, l_desc_tab);

    if l_column_cnt < 2
       or upper(l_desc_tab(1).col_name) <> 'D'
       or upper(l_desc_tab(2).col_name) <> 'R'
    then
      raise_application_error(
        -20000,
        'Preference LOV query must return columns aliased as d and r for pref_key=' || p_pref_key
      );
    end if;

    dbms_sql.define_column(l_cursor, 1, l_display, 4000);
    dbms_sql.define_column(l_cursor, 2, l_return, 4000);

    l_status := dbms_sql.execute(l_cursor);

    while dbms_sql.fetch_rows(l_cursor) > 0 loop
      dbms_sql.column_value(l_cursor, 1, l_display);
      dbms_sql.column_value(l_cursor, 2, l_return);
      append_row(
        p_rows          => p_rows,
        p_display_value => l_display,
        p_return_value  => l_return
      );
    end loop;

    dbms_sql.close_cursor(l_cursor);
  exception
    when others then
      if dbms_sql.is_open(l_cursor) then
        dbms_sql.close_cursor(l_cursor);
      end if;
      raise;
  end append_dynamic_lov_rows;

  procedure append_weather_location_rows(
    p_rows          in out nocopy json_array_t,
    p_search        in varchar2,
    p_current_value in varchar2,
    p_limit         in pls_integer
  ) is
    l_search   varchar2(4000) := trim(p_search);
    l_response clob;
  begin
    if (l_search is null or length(l_search) < 3)
       and p_current_value is not null
       and not regexp_like(p_current_value, '^\s*\{')
    then
      l_search := p_current_value;
    end if;

    if l_search is null or length(l_search) < 3 then
      append_current_weather_location(
        p_rows          => p_rows,
        p_current_value => p_current_value
      );
      return;
    end if;

    l_response := http_get(
      gc_open_meteo_geocoder_url
      || '?name=' || utl_url.escape(l_search, true, 'AL32UTF8')
      || chr(38) || 'count=' || to_char(p_limit)
      || chr(38) || 'language=en'
      || chr(38) || 'format=json'
    );

    for rec in (
      select jt.name,
             jt.latitude,
             jt.longitude,
             jt.timezone,
             jt.country,
             jt.admin1
        from json_table(
               l_response,
               '$.results[*]'
               columns (
                 name varchar2(255) path '$.name',
                 latitude number path '$.latitude',
                 longitude number path '$.longitude',
                 timezone varchar2(255) path '$.timezone',
                 country varchar2(255) path '$.country',
                 admin1 varchar2(255) path '$.admin1'
               )
             ) jt
    ) loop
      append_location_row(
        p_rows      => p_rows,
        p_name      => rec.name,
        p_latitude  => rec.latitude,
        p_longitude => rec.longitude,
        p_timezone  => rec.timezone,
        p_country   => rec.country,
        p_admin1    => rec.admin1
      );
    end loop;
  exception
    when others then
      append_current_weather_location(
        p_rows          => p_rows,
        p_current_value => p_current_value
      );
  end append_weather_location_rows;

  function get_lov_json(
    p_pref_key      in orac_api.preference_definitions_v.pref_key%type,
    p_search        in varchar2 default null,
    p_current_value in varchar2 default null,
    p_limit         in pls_integer default 50
  ) return clob is
    l_pref_definition t_pref_definition;
    l_rows            json_array_t := json_array_t();
    l_app_id          number := current_app_id;
    l_limit           pls_integer := least(greatest(nvl(p_limit, 50), 1), 100);
  begin
    load_preference_definition(
      p_pref_key         => p_pref_key,
      p_pref_definition  => l_pref_definition
    );

    if l_pref_definition.is_active <> 'Y' then
      return l_rows.to_clob;
    end if;

    if l_pref_definition.pref_key = 'weather_location' then
      append_weather_location_rows(
        p_rows          => l_rows,
        p_search        => p_search,
        p_current_value => p_current_value,
        p_limit         => l_limit
      );
      return l_rows.to_clob;
    end if;

    if l_pref_definition.lov_type is null then
      return l_rows.to_clob;
    end if;

    case l_pref_definition.lov_type
      when 'static' then
        append_static_lov_rows(
          p_rows            => l_rows,
          p_static_lov_code => l_pref_definition.static_lov_code
        );
      when 'sql' then
        append_dynamic_lov_rows(
          p_rows          => l_rows,
          p_pref_key      => l_pref_definition.pref_key,
          p_lov_query     => l_pref_definition.lov_query,
          p_app_id        => l_app_id,
          p_search        => p_search,
          p_current_value => p_current_value,
          p_limit         => l_limit
        );
      else
        return l_rows.to_clob;
    end case;

    return l_rows.to_clob;
  exception
    when others then
      raise_application_error(
        -20000,
        'Preference LOV resolution failed for pref_key='
        || nvl(lower(trim(p_pref_key)), '<null>')
        || ': '
        || sqlerrm
      );
  end get_lov_json;
end preference_lov_api;
/

--rollback drop package body orac_code.preference_lov_api;
