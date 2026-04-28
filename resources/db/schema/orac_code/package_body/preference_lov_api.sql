-- __author__: clive
-- __date__: 2026-04-27
-- __description__: ORAC_CODE helper for preference-driven LOV resolution

create or replace package body orac_code.preference_lov_api as
  gc_default_app_id constant number := 1042;
  gc_open_meteo_geocoder_url constant varchar2(200) := 'https://geocoding-api.open-meteo.com/v1/search';

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
    p_rows         in out nocopy json_array_t,
    p_display_value in varchar2,
    p_return_value  in varchar2
  ) is
    l_row json_object_t := json_object_t();
  begin
    l_row.put('display_value', p_display_value);
    l_row.put('return_value', p_return_value);
    p_rows.append(l_row);
  end append_row;

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

  function get_lov_json(
    p_pref_key      in orac_api.preference_definitions_v.pref_key%type,
    p_search        in varchar2 default null,
    p_current_value in varchar2 default null
  ) return clob is
    l_pref_key  varchar2(100) := lower(trim(p_pref_key));
    l_search    varchar2(4000) := trim(p_search);
    l_response  clob;
    l_rows      json_array_t := json_array_t();
    l_app_id    number := current_app_id;
  begin
    case l_pref_key
      when 'date_format' then
        append_row(l_rows, 'DD-MON-YYYY HH24:MI', 'DD-MON-YYYY HH24:MI');
        append_row(l_rows, 'YYYY-MM-DD HH24:MI', 'YYYY-MM-DD HH24:MI');
        append_row(l_rows, 'DD/MM/YYYY HH24:MI', 'DD/MM/YYYY HH24:MI');
        append_row(l_rows, 'DD Mon YYYY HH24:MI', 'DD Mon YYYY HH24:MI');

      when 'default_llm_id' then
        for rec in (
          select llm_id,
                 name,
                 provider
            from orac_api.llm_registry_v
           where is_enabled = 'Y'
           order by provider, name
        ) loop
          append_row(
            l_rows,
            rec.name || ' (' || rec.provider || ')',
            to_char(rec.llm_id)
          );
        end loop;

      when 'landing_page_id' then
        for rec in (
          select page_id,
                 page_name
            from apex_application_pages
           where application_id = l_app_id
             and page_id not in (0, 9999)
           order by page_id
        ) loop
          append_row(
            l_rows,
            rec.page_name || ' (' || rec.page_id || ')',
            to_char(rec.page_id)
          );
        end loop;

      when 'theme_style' then
        for rec in (
          select name,
                 is_current
            from apex_application_theme_styles
           where application_id = l_app_id
             and is_public = 'Yes'
           order by case is_current
                      when 'Yes' then 0
                      else 1
                    end,
                    name
        ) loop
          append_row(l_rows, rec.name, rec.name);
        end loop;

      when 'timezone' then
        for rec in (
          select display_label,
                 tz_name
            from orac_api.timezones_v
           where is_active = 'Y'
           order by region_group, display_sequence, display_label
        ) loop
          append_row(l_rows, rec.display_label, rec.tz_name);
        end loop;

      when 'tts_voice' then
        append_row(l_rows, 'English (UK) Female 1', 'en-GB-female-1');
        append_row(l_rows, 'English (UK) Male 1', 'en-GB-male-1');
        append_row(l_rows, 'English (US) Female 1', 'en-US-female-1');
        append_row(l_rows, 'English (US) Male 1', 'en-US-male-1');

      when 'weather_location' then
        if l_search is null or length(l_search) < 3 then
          append_current_weather_location(
            p_rows          => l_rows,
            p_current_value => p_current_value
          );
          return l_rows.to_clob;
        end if;

        l_response := apex_web_service.make_rest_request(
          p_url         => gc_open_meteo_geocoder_url
                           || '?name=' || utl_url.escape(l_search, true, 'AL32UTF8')
                           || chr(38) || 'count=10'
                           || chr(38) || 'language=en'
                           || chr(38) || 'format=json',
          p_http_method => 'GET'
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
            p_rows      => l_rows,
            p_name      => rec.name,
            p_latitude  => rec.latitude,
            p_longitude => rec.longitude,
            p_timezone  => rec.timezone,
            p_country   => rec.country,
            p_admin1    => rec.admin1
          );
        end loop;
    end case;

    return l_rows.to_clob;
  exception
    when others then
      return json_array_t().to_clob;
  end get_lov_json;
end preference_lov_api;
/
