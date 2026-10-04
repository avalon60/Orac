--liquibase formatted sql

--changeset clive:create_package_body_orac_code_package_body_user_preferences_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-04-29
-- __description__: ORAC_CODE wrapper API for user preference maintenance

create or replace package body orac_code.user_preferences_api as
  gc_default_app_id constant number := 1042;
  gc_system_username constant varchar2(100) := 'system';
  gc_general_chat_key constant varchar2(100) := 'general_chat_llm';

  function is_system_scalar_key(
    p_pref_key in varchar2
  ) return boolean
  is
  begin
    return lower(trim(p_pref_key)) in (
      'max_tokens',
      'show_reasoning',
      'strip_reasoning_tags'
    );
  end is_system_scalar_key;

  function is_protected_system_key(
    p_pref_key in varchar2
  ) return boolean
  is
  begin
    return lower(trim(p_pref_key)) = gc_general_chat_key
        or is_system_scalar_key(p_pref_key);
  end is_protected_system_key;

  function current_app_id return number
  as
    l_app_id_txt varchar2(100);
  begin
    l_app_id_txt := nullif(sys_context('APEX$SESSION', 'APP_ID'), '');

    if l_app_id_txt is not null and regexp_like(l_app_id_txt, '^\d+$') then
      return to_number(l_app_id_txt);
    end if;

    return gc_default_app_id;
  end current_app_id;

  function serialise_pref_value(
    p_pref_value in orac_api.user_preferences_v.pref_value%type
  ) return varchar2
  as
    l_value_txt varchar2(4000);
  begin
    if p_pref_value is null then
      return null;
    end if;

    select json_serialize(p_pref_value returning varchar2(4000) null on error)
      into l_value_txt
      from dual;

    return l_value_txt;
  end serialise_pref_value;

  function report_validation_failure(
    p_message             in varchar2,
    p_apex_page_item_name in varchar2 default null
  ) return varchar2
  as
    l_app_id_txt varchar2(100);
    l_page_item  varchar2(255);
  begin
    l_app_id_txt := nullif(sys_context('APEX$SESSION', 'APP_ID'), '');
    l_page_item := nullif(trim(p_apex_page_item_name), '');

    if l_app_id_txt is not null then
      if l_page_item is not null then
        apex_error.add_error(
          p_message          => p_message,
          p_display_location => apex_error.c_inline_with_field_and_notif,
          p_page_item_name   => l_page_item
        );
      else
        apex_error.add_error(
          p_message          => p_message,
          p_display_location => apex_error.c_inline_in_notification
        );
      end if;
    end if;

    return p_message;
  end report_validation_failure;

  function select_value_allowed(
    p_pref_key        in orac_api.user_preferences_v.pref_key%type,
    p_lov_type        in orac_api.preference_definitions_v.lov_type%type,
    p_lov_query       in orac_api.preference_definitions_v.lov_query%type,
    p_current_value   in varchar2,
    p_allow_zero_lov  in boolean
  ) return boolean
  as
    l_match_count number;
    l_cursor      integer;
    l_status      integer;
    l_column_cnt  pls_integer;
    l_desc_tab    dbms_sql.desc_tab2;
    l_display     varchar2(4000);
    l_return      varchar2(4000);
    l_app_id      number := current_app_id;
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
    if p_current_value is null then
      return true;
    end if;

    if p_allow_zero_lov and trim(p_current_value) = '0' then
      return true;
    end if;

    if lower(p_lov_type) = 'static' then
      select count(*)
        into l_match_count
        from json_table(
               orac_code.preference_lov_api.get_lov_json(
                 p_pref_key      => p_pref_key,
                 p_search        => null,
                 p_current_value => p_current_value
               ),
               '$[*]'
               columns (
                 return_value varchar2(4000) path '$.return_value'
               )
             ) jt
       where jt.return_value = p_current_value;

      return l_match_count > 0;
    end if;

    if lower(p_lov_type) <> 'sql' or trim(p_lov_query) is null then
      return true;
    end if;

    l_cursor := dbms_sql.open_cursor;
    dbms_sql.parse(l_cursor, p_lov_query, dbms_sql.native);
    bind_number_if_present('APP_ID', l_app_id);
    bind_if_present('APEX$SEARCH', null);
    bind_if_present('P_SEARCH', null);
    bind_if_present('CURRENT_VALUE', p_current_value);
    bind_if_present('P_CURRENT_VALUE', p_current_value);
    bind_if_present('PREF_KEY', p_pref_key);
    bind_number_if_present('P_LIMIT', 100);

    dbms_sql.describe_columns2(l_cursor, l_column_cnt, l_desc_tab);
    if l_column_cnt < 2
       or upper(l_desc_tab(1).col_name) <> 'D'
       or upper(l_desc_tab(2).col_name) <> 'R' then
      raise_application_error(
        -20016,
        'Selectable preference "' || p_pref_key || '" must expose LOV columns aliased as d and r.'
      );
    end if;

    dbms_sql.define_column(l_cursor, 1, l_display, 4000);
    dbms_sql.define_column(l_cursor, 2, l_return, 4000);
    l_status := dbms_sql.execute(l_cursor);

    while dbms_sql.fetch_rows(l_cursor) > 0 loop
      dbms_sql.column_value(l_cursor, 2, l_return);
      if l_return = p_current_value then
        dbms_sql.close_cursor(l_cursor);
        return true;
      end if;
    end loop;

    dbms_sql.close_cursor(l_cursor);

    return false;
  exception
    when others then
      if dbms_sql.is_open(l_cursor) then
        dbms_sql.close_cursor(l_cursor);
      end if;
      raise_application_error(
        -20015,
        'Unable to validate selectable value for preference "' || p_pref_key || '": ' || sqlerrm
      );
  end select_value_allowed;

  function validate_catalogue_value(
    p_pref_key             in orac_api.user_preferences_v.pref_key%type,
    p_pref_value           in orac_api.user_preferences_v.pref_value%type,
    p_value_type           in orac_api.preference_definitions_v.value_type%type default null,
    p_apex_page_item_name  in varchar2 default null,
    p_require_user_editable in boolean default true
  ) return varchar2
  as
    l_pref_definition   orac_api.preference_definitions_v%rowtype;
    l_value_type        orac_api.preference_definitions_v.value_type%type;
    l_display_label     orac_api.preference_definitions_v.display_label%type;
    l_string_value      varchar2(4000);
    l_boolean_value     varchar2(10);
    l_serialised_value  varchar2(4000);
    l_is_string_value   varchar2(1);
    l_number_value      number;
    l_step_remainder    number;
    l_allow_zero_lov    boolean := false;

    function fail(
      p_message in varchar2
    ) return varchar2
    as
    begin
      return report_validation_failure(
        p_message             => p_message,
        p_apex_page_item_name => p_apex_page_item_name
      );
    end fail;
  begin
    begin
      select *
        into l_pref_definition
        from orac_api.preference_definitions_v
       where pref_key = p_pref_key;
    exception
      when no_data_found then
        return fail('Unknown preference key: ' || p_pref_key);
    end;

    l_value_type := coalesce(p_value_type, l_pref_definition.value_type);
    l_display_label := coalesce(l_pref_definition.display_label, p_pref_key);

    if nvl(l_pref_definition.is_active, 'N') <> 'Y' then
      return fail('Preference "' || l_display_label || '" is not active.');
    end if;

    if p_require_user_editable
       and nvl(l_pref_definition.is_user_editable, 'N') <> 'Y' then
      return fail('Preference "' || l_display_label || '" is not editable.');
    end if;

    if l_value_type <> l_pref_definition.value_type then
      return fail(
        'Preference "' || l_display_label || '" expects value type '
        || l_pref_definition.value_type || '.'
      );
    end if;

    if l_pref_definition.control_type = 'slider' then
      if l_pref_definition.value_type <> 'number'
         or l_pref_definition.min_number is null
         or l_pref_definition.max_number is null
         or l_pref_definition.step_number is null
         or l_pref_definition.step_number <= 0
         or l_pref_definition.min_number > l_pref_definition.max_number then
        return fail(
          'Preference "' || l_display_label || '" has invalid slider metadata.'
        );
      end if;
    end if;

    l_serialised_value := serialise_pref_value(p_pref_value);

    select case
             when json_exists(p_pref_value, '$?(@.type() == "string")') then 'Y'
             else 'N'
           end,
           json_value(p_pref_value, '$' returning varchar2(4000) null on error),
           json_value(p_pref_value, '$' returning number null on error),
           lower(json_value(p_pref_value, '$' returning varchar2(10) null on error))
      into l_is_string_value,
           l_string_value,
           l_number_value,
           l_boolean_value
      from dual;

    if nvl(l_pref_definition.is_required, 'N') = 'Y' then
      if l_value_type = 'string' and trim(l_string_value) is null then
        return fail('Preference "' || l_display_label || '" is required.');
      elsif l_value_type = 'number' and l_number_value is null then
        return fail('Preference "' || l_display_label || '" is required.');
      elsif l_value_type = 'boolean' and l_boolean_value not in ('true', 'false') then
        return fail('Preference "' || l_display_label || '" is required.');
      elsif l_value_type = 'json' and (l_serialised_value is null or trim(l_serialised_value) = 'null') then
        return fail('Preference "' || l_display_label || '" is required.');
      end if;
    end if;

    if l_value_type = 'string' then
      if l_string_value is null
         and l_serialised_value is not null
         and l_is_string_value <> 'Y' then
        return fail('Preference "' || l_display_label || '" must be stored as text.');
      end if;

      if l_pref_definition.min_length is not null
         and length(l_string_value) < l_pref_definition.min_length then
        return fail(
          'Preference "' || l_display_label || '" must be at least '
          || l_pref_definition.min_length || ' characters.'
        );
      end if;

      if l_pref_definition.max_length is not null
         and length(l_string_value) > l_pref_definition.max_length then
        return fail(
          'Preference "' || l_display_label || '" must be at most '
          || l_pref_definition.max_length || ' characters.'
        );
      end if;

      if l_pref_definition.regex_pattern is not null
         and l_string_value is not null
         and not regexp_like(l_string_value, l_pref_definition.regex_pattern) then
        return fail('Preference "' || l_display_label || '" has an invalid format.');
      end if;
    elsif l_value_type = 'number' then
      if l_number_value is null and l_serialised_value is not null then
        return fail('Preference "' || l_display_label || '" must be numeric.');
      end if;

      if l_pref_definition.min_number is not null
         and l_number_value < l_pref_definition.min_number then
        return fail(
          'Preference "' || l_display_label || '" must be at least '
          || to_char(l_pref_definition.min_number) || '.'
        );
      end if;

      if l_pref_definition.max_number is not null
         and l_number_value > l_pref_definition.max_number then
        return fail(
          'Preference "' || l_display_label || '" must be at most '
          || to_char(l_pref_definition.max_number) || '.'
        );
      end if;

      if l_pref_definition.step_number is not null
         and l_pref_definition.step_number <= 0 then
        return fail(
          'Preference "' || l_display_label || '" has invalid step metadata.'
        );
      end if;

      if l_pref_definition.step_number is not null
         and l_number_value is not null then
        l_step_remainder := mod(
          l_number_value - coalesce(l_pref_definition.min_number, 0),
          l_pref_definition.step_number
        );

        if l_step_remainder <> 0 then
          return fail(
            'Preference "' || l_display_label
            || '" must align to step '
            || to_char(l_pref_definition.step_number) || '.'
          );
        end if;
      end if;
    elsif l_value_type = 'boolean' then
      if l_boolean_value is not null and l_boolean_value not in ('true', 'false') then
        return fail('Preference "' || l_display_label || '" must be true or false.');
      end if;
    elsif l_value_type = 'json' then
      if l_serialised_value is null and p_pref_value is not null then
        return fail('Preference "' || l_display_label || '" must contain valid JSON.');
      end if;
    else
      return fail(
        'Preference "' || l_display_label || '" has unsupported value type '
        || l_value_type || '.'
      );
    end if;

    if l_pref_definition.control_type in ('select_list', 'popup_lov')
       and l_pref_definition.lov_type is not null
       and l_value_type in ('string', 'number') then
      l_allow_zero_lov := (
           l_value_type = 'number'
       and l_number_value = 0
       and l_pref_definition.default_value is not null
       and serialise_pref_value(l_pref_definition.default_value) = '0'
      );

      if not select_value_allowed(
        p_pref_key       => p_pref_key,
        p_lov_type       => l_pref_definition.lov_type,
        p_lov_query      => l_pref_definition.lov_query,
        p_current_value  => case
                              when l_value_type = 'number' then to_char(l_number_value)
                              else l_string_value
                            end,
        p_allow_zero_lov => l_allow_zero_lov
      ) then
        return fail(
          'Preference "' || l_display_label
          || '" must use one of the available selections.'
        );
      end if;
    end if;

    return null;
  end validate_catalogue_value;

  function validate_preference_value(
    p_pref_key             in orac_api.user_preferences_v.pref_key%type,
    p_pref_value           in orac_api.user_preferences_v.pref_value%type,
    p_value_type           in orac_api.preference_definitions_v.value_type%type default null,
    p_apex_page_item_name  in varchar2 default null
  ) return varchar2
  as
  begin
    return validate_catalogue_value(
      p_pref_key              => p_pref_key,
      p_pref_value            => p_pref_value,
      p_value_type            => p_value_type,
      p_apex_page_item_name   => p_apex_page_item_name,
      p_require_user_editable => true
    );
  end validate_preference_value;

  procedure assert_valid_preference_value(
    p_pref_key             in orac_api.user_preferences_v.pref_key%type,
    p_pref_value           in orac_api.user_preferences_v.pref_value%type,
    p_value_type           in orac_api.preference_definitions_v.value_type%type,
    p_apex_page_item_name  in varchar2 default null
  ) as
    l_error_message varchar2(4000);
  begin
    l_error_message := validate_preference_value(
      p_pref_key             => p_pref_key,
      p_pref_value           => p_pref_value,
      p_value_type           => p_value_type,
      p_apex_page_item_name  => p_apex_page_item_name
    );

    if l_error_message is not null then
      raise_application_error(-20005, l_error_message);
    end if;
  end assert_valid_preference_value;

  procedure assert_ordinary_target_allowed(
    p_user_id  in orac_api.user_preferences_v.user_id%type,
    p_pref_key in orac_api.user_preferences_v.pref_key%type
  ) is
    l_system_count number;
  begin
    select count(*)
      into l_system_count
      from orac_api.users_v
     where user_id = p_user_id
       and lower(username) = gc_system_username;

    if l_system_count > 0 or is_protected_system_key(p_pref_key)
    then
      raise_application_error(
        -20075,
        'System preferences must be maintained through the dedicated system API.'
      );
    end if;
  end assert_ordinary_target_allowed;

  procedure assert_existing_row_allowed(
    p_pref_id in orac_api.user_preferences_v.pref_id%type
  ) is
    l_user_id  orac_api.user_preferences_v.user_id%type;
    l_pref_key orac_api.user_preferences_v.pref_key%type;
  begin
    select user_id, pref_key
      into l_user_id, l_pref_key
      from orac_api.user_preferences_v
     where pref_id = p_pref_id;
    assert_ordinary_target_allowed(l_user_id, l_pref_key);
  exception
    when no_data_found then
      null;
  end assert_existing_row_allowed;

  procedure ins(
    p_pref_id      in out orac_api.user_preferences_v.pref_id%type,
    p_user_id      in     orac_api.user_preferences_v.user_id%type,
    p_pref_key     in     orac_api.user_preferences_v.pref_key%type,
    p_pref_value   in     orac_api.user_preferences_v.pref_value%type,
    p_value_type   in     orac_api.preference_definitions_v.value_type%type,
    p_row_version     out orac_api.user_preferences_v.row_version%type,
    p_apex_page_item_name in varchar2 default null
  ) as
  begin
    assert_ordinary_target_allowed(p_user_id, p_pref_key);
    assert_valid_preference_value(
      p_pref_key             => p_pref_key,
      p_pref_value           => p_pref_value,
      p_value_type           => p_value_type,
      p_apex_page_item_name  => p_apex_page_item_name
    );

    orac_api.user_preferences_tapi.ins(
      p_pref_id     => p_pref_id,
      p_user_id     => p_user_id,
      p_pref_key    => p_pref_key,
      p_pref_value  => p_pref_value,
      p_row_version => p_row_version
    );
  end ins;

  procedure upd(
    p_pref_id      in out orac_api.user_preferences_v.pref_id%type,
    p_user_id      in     orac_api.user_preferences_v.user_id%type,
    p_pref_key     in     orac_api.user_preferences_v.pref_key%type,
    p_pref_value   in     orac_api.user_preferences_v.pref_value%type,
    p_value_type   in     orac_api.preference_definitions_v.value_type%type,
    p_row_version     out orac_api.user_preferences_v.row_version%type,
    p_apex_page_item_name in varchar2 default null
  ) as
  begin
    assert_existing_row_allowed(p_pref_id);
    assert_ordinary_target_allowed(p_user_id, p_pref_key);
    assert_valid_preference_value(
      p_pref_key             => p_pref_key,
      p_pref_value           => p_pref_value,
      p_value_type           => p_value_type,
      p_apex_page_item_name  => p_apex_page_item_name
    );

    orac_api.user_preferences_tapi.upd(
      p_pref_id     => p_pref_id,
      p_user_id     => p_user_id,
      p_pref_key    => p_pref_key,
      p_pref_value  => p_pref_value,
      p_row_version => p_row_version
    );
  end upd;

  procedure del(
    p_pref_id      in out orac_api.user_preferences_v.pref_id%type,
    p_row_version     out orac_api.user_preferences_v.row_version%type
  ) as
  begin
    assert_existing_row_allowed(p_pref_id);
    orac_api.user_preferences_tapi.del(
      p_pref_id     => p_pref_id,
      p_row_version => p_row_version
    );
  end del;

  function get_system_user_id return number
  is
    l_user_id orac_api.users_v.user_id%type;
  begin
    select user_id
      into l_user_id
      from orac_api.users_v
     where username = gc_system_username
       and is_active = 'N';
    return l_user_id;
  exception
    when no_data_found then
      raise_application_error(-20073, 'Reserved SYSTEM principal is not provisioned.');
  end get_system_user_id;

  function normalise_system_scalar(
    p_pref_key in orac_api.user_preferences_v.pref_key%type,
    p_value    in varchar2
  ) return varchar2
  is
    l_error_message varchar2(4000);
    l_normalised    varchar2(4000);
    l_pref_value    orac_api.user_preferences_v.pref_value%type;
  begin
    if not is_system_scalar_key(p_pref_key) or trim(p_value) is null
    then
      return null;
    end if;

    if lower(trim(p_pref_key)) = 'max_tokens'
    then
      if not regexp_like(trim(p_value), '^\d+$')
      then
        return null;
      end if;
      l_normalised := to_char(to_number(trim(p_value)));
    else
      l_normalised := lower(trim(p_value));
      if l_normalised not in ('true', 'false')
      then
        return null;
      end if;
    end if;

    l_pref_value := json(l_normalised);
    l_error_message := validate_catalogue_value(
      p_pref_key              => lower(trim(p_pref_key)),
      p_pref_value            => l_pref_value,
      p_value_type            => null,
      p_require_user_editable => false
    );
    if l_error_message is not null
    then
      return null;
    end if;
    return l_normalised;
  exception
    when others then
      return null;
  end normalise_system_scalar;

  function get_system_scalar(
    p_pref_key in orac_api.user_preferences_v.pref_key%type
  ) return varchar2
  is
    l_pref_value varchar2(4000);
    l_system_id  orac_api.users_v.user_id%type;
  begin
    if not is_system_scalar_key(p_pref_key)
    then
      raise_application_error(-20076, 'Unsupported system scalar preference key.');
    end if;

    l_system_id := get_system_user_id;
    select json_serialize(pref_value returning varchar2(4000) null on error)
      into l_pref_value
      from orac_api.user_preferences_v
     where user_id = l_system_id
       and pref_key = lower(trim(p_pref_key));
    return normalise_system_scalar(p_pref_key, l_pref_value);
  exception
    when no_data_found then
      return null;
  end get_system_scalar;

  procedure set_system_scalar(
    p_pref_key   in orac_api.user_preferences_v.pref_key%type,
    p_pref_value in orac_api.user_preferences_v.pref_value%type
  ) is
    l_pref_id      orac_api.user_preferences_v.pref_id%type;
    l_row_version  orac_api.user_preferences_v.row_version%type;
    l_system_id    orac_api.users_v.user_id%type;
    l_serialised   varchar2(4000);
    l_normalised   varchar2(4000);
    l_value        orac_api.user_preferences_v.pref_value%type;
  begin
    if not is_system_scalar_key(p_pref_key)
    then
      raise_application_error(-20076, 'Unsupported system scalar preference key.');
    end if;

    l_serialised := serialise_pref_value(p_pref_value);
    l_normalised := normalise_system_scalar(p_pref_key, l_serialised);
    if l_normalised is null
    then
      raise_application_error(-20077, 'Invalid system scalar preference value.');
    end if;

    l_value := json(l_normalised);
    l_system_id := get_system_user_id;
    begin
      select pref_id, row_version
        into l_pref_id, l_row_version
        from orac_api.user_preferences_v
       where user_id = l_system_id
         and pref_key = lower(trim(p_pref_key));
      orac_api.user_preferences_tapi.upd(
        p_pref_id     => l_pref_id,
        p_user_id     => l_system_id,
        p_pref_key    => lower(trim(p_pref_key)),
        p_pref_value  => l_value,
        p_row_version => l_row_version
      );
    exception
      when no_data_found then
        l_pref_id := null;
        orac_api.user_preferences_tapi.ins(
          p_pref_id     => l_pref_id,
          p_user_id     => l_system_id,
          p_pref_key    => lower(trim(p_pref_key)),
          p_pref_value  => l_value,
          p_row_version => l_row_version
        );
    end;
  end set_system_scalar;

  procedure migrate_system_scalar(
    p_pref_key     in orac_api.user_preferences_v.pref_key%type,
    p_config_value in varchar2
  ) is
    l_candidate       varchar2(4000);
    l_consensus       varchar2(4000);
    l_normalised      varchar2(4000);
    l_user_count      number := 0;
    l_valid_count     number := 0;
    l_has_conflict    boolean := false;
    l_system_id       orac_api.users_v.user_id%type;
    l_default_value   varchar2(4000);
    l_value           orac_api.user_preferences_v.pref_value%type;
  begin
    if not is_system_scalar_key(p_pref_key)
    then
      raise_application_error(-20076, 'Unsupported system scalar preference key.');
    end if;

    l_system_id := get_system_user_id;
    l_candidate := get_system_scalar(p_pref_key);

    if l_candidate is null
    then
      for rec in (
        select u.user_id,
               json_serialize(p.pref_value returning varchar2(4000) null on error) as pref_value
          from orac_api.users_v u
          left join orac_api.user_preferences_v p
            on p.user_id = u.user_id
           and p.pref_key = lower(trim(p_pref_key))
         where u.is_active = 'Y'
           and lower(u.username) <> gc_system_username
      ) loop
        l_user_count := l_user_count + 1;
        l_normalised := normalise_system_scalar(p_pref_key, rec.pref_value);
        if l_normalised is not null
        then
          l_valid_count := l_valid_count + 1;
          if l_consensus is null
          then
            l_consensus := l_normalised;
          elsif l_consensus <> l_normalised
          then
            l_has_conflict := true;
          end if;
        end if;
      end loop;

      if l_user_count > 0
         and l_valid_count = l_user_count
         and not l_has_conflict
      then
        l_candidate := l_consensus;
      end if;
    end if;

    if l_candidate is null
    then
      l_candidate := normalise_system_scalar(p_pref_key, p_config_value);
    end if;

    if l_candidate is null
    then
      select json_serialize(default_value returning varchar2(4000) null on error)
        into l_default_value
        from orac_api.preference_definitions_v
       where pref_key = lower(trim(p_pref_key))
         and is_active = 'Y';
      l_candidate := normalise_system_scalar(p_pref_key, l_default_value);
    end if;

    if l_candidate is null
    then
      raise_application_error(-20078, 'System scalar catalogue fallback is invalid.');
    end if;

    l_value := json(l_candidate);
    set_system_scalar(p_pref_key, l_value);

    for rec in (
      select p.pref_id, p.row_version
        from orac_api.user_preferences_v p
        join orac_api.users_v u
          on u.user_id = p.user_id
       where p.pref_key = lower(trim(p_pref_key))
         and u.user_id <> l_system_id
    ) loop
      orac_api.user_preferences_tapi.del(
        p_pref_id     => rec.pref_id,
        p_row_version => rec.row_version
      );
    end loop;
  end migrate_system_scalar;

  procedure assert_general_chat_llm(
    p_llm_id in number
  ) is
    l_count number;
  begin
    select count(*)
      into l_count
      from orac_api.llm_registry_v
     where llm_id = p_llm_id
       and is_enabled = 'Y';
    if l_count = 0
    then
      raise_application_error(-20074, 'General Chat LLM must be an enabled registry model.');
    end if;
  end assert_general_chat_llm;

  function get_system_general_chat_llm return number
  is
    l_llm_id    number;
    l_system_id orac_api.users_v.user_id%type;
  begin
    l_system_id := get_system_user_id;
    select json_value(pref_value, '$' returning number error on error)
      into l_llm_id
      from orac_api.user_preferences_v
     where user_id = l_system_id
       and pref_key = gc_general_chat_key;
    return l_llm_id;
  exception
    when no_data_found then
      return null;
  end get_system_general_chat_llm;

  procedure set_system_general_chat_llm(
    p_llm_id in number
  ) is
    l_pref_id     orac_api.user_preferences_v.pref_id%type;
    l_row_version orac_api.user_preferences_v.row_version%type;
    l_system_id   orac_api.users_v.user_id%type;
  begin
    assert_general_chat_llm(p_llm_id);
    l_system_id := get_system_user_id;
    begin
      select pref_id, row_version
        into l_pref_id, l_row_version
        from orac_api.user_preferences_v
       where user_id = l_system_id
         and pref_key = gc_general_chat_key;
      orac_api.user_preferences_tapi.upd(
        p_pref_id     => l_pref_id,
        p_user_id     => l_system_id,
        p_pref_key    => gc_general_chat_key,
        p_pref_value  => json(to_char(p_llm_id)),
        p_row_version => l_row_version
      );
    exception
      when no_data_found then
        l_pref_id := null;
        orac_api.user_preferences_tapi.ins(
          p_pref_id     => l_pref_id,
          p_user_id     => l_system_id,
          p_pref_key    => gc_general_chat_key,
          p_pref_value  => json(to_char(p_llm_id)),
          p_row_version => l_row_version
        );
    end;
  end set_system_general_chat_llm;

  procedure migrate_general_chat_llm(
    p_config_provider in varchar2,
    p_config_model    in varchar2
  ) is
    l_canonical_id number;
    l_config_id    number;
    l_history_id   number;
    l_user_count   number;
    l_valid_count  number;
    l_distinct_ids number;
    l_selected_id  number;
  begin
    begin
      l_canonical_id := get_system_general_chat_llm;
      assert_general_chat_llm(l_canonical_id);
      l_selected_id := l_canonical_id;
    exception
      when others then
        l_selected_id := null;
    end;

    if l_selected_id is null
    then
      select count(*),
             count(r.llm_id),
             count(distinct r.llm_id),
             min(r.llm_id)
        into l_user_count, l_valid_count, l_distinct_ids, l_history_id
        from orac_api.users_v u
        left join orac_api.user_preferences_v p
          on p.user_id = u.user_id
         and p.pref_key = 'default_llm_id'
        left join orac_api.llm_registry_v r
          on r.llm_id = json_value(p.pref_value, '$' returning number null on error)
         and r.is_enabled = 'Y'
       where u.username <> gc_system_username
         and u.is_active = 'Y';

      if l_user_count > 0
         and l_valid_count = l_user_count
         and l_distinct_ids = 1
      then
        l_selected_id := l_history_id;
      end if;
    end if;

    if l_selected_id is null
    then
      begin
        select llm_id
          into l_config_id
          from orac_api.llm_registry_v
         where lower(provider) = lower(trim(p_config_provider))
           and model = trim(p_config_model)
           and is_enabled = 'Y'
         fetch first 1 row only;
        l_selected_id := l_config_id;
      exception
        when no_data_found then
          return;
      end;
    end if;

    set_system_general_chat_llm(l_selected_id);
    for rec in (
      select pref_id, row_version
        from orac_api.user_preferences_v
       where pref_key = 'default_llm_id'
    ) loop
      orac_api.user_preferences_tapi.del(
        p_pref_id     => rec.pref_id,
        p_row_version => rec.row_version
      );
    end loop;
  end migrate_general_chat_llm;
end user_preferences_api;
/

--rollback drop package body orac_code.user_preferences_api;
