--liquibase formatted sql

--changeset clive:create_package_body_orac_code_package_body_apex_return_nav_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-07-07
-- __description__: validated cross-application APEX return navigation API body

create or replace package body orac_code.apex_return_nav_api as
  c_admin_app_id constant number := 1042;
  c_plugin_app_id constant number := 1043;
  c_stack_item_name constant varchar2(30 char) := 'ORAC_NAV_STACK';

  type t_frame is record (
    app_id  number,
    page_id number
  );

  type t_stack is table of t_frame index by pls_integer;

  function current_stack_value(
    p_stack in varchar2
  ) return varchar2
  is
  begin
    return coalesce(p_stack, v(c_stack_item_name));
  end current_stack_value;

  function is_valid_frame(
    p_app_id  in number,
    p_page_id in number
  ) return boolean
  is
    l_exists number;
  begin
    if p_app_id = c_admin_app_id and p_page_id > 0
    then
      return true;
    end if;

    if p_app_id = c_plugin_app_id and p_page_id in (1, 2)
    then
      return true;
    end if;

    select count(*)
      into l_exists
      from orac_code.plugin_apex_app_menu_v menu
     where menu.installed_app_id = p_app_id
       and p_page_id > 0
       and rownum = 1;

    return l_exists > 0;
  exception
    when others then
      return false;
  end is_valid_frame;

  procedure append_frame(
    p_stack   in out nocopy t_stack,
    p_count   in out nocopy pls_integer,
    p_app_id  in number,
    p_page_id in number
  )
  is
    l_existing pls_integer;
    l_keep_from pls_integer;
  begin
    if not is_valid_frame(p_app_id, p_page_id)
    then
      return;
    end if;

    for i in 1 .. p_count
    loop
      if p_stack(i).app_id = p_app_id and p_stack(i).page_id = p_page_id
      then
        l_existing := i;
        exit;
      end if;
    end loop;

    if l_existing is not null
    then
      p_count := l_existing - 1;
    end if;

    p_count := p_count + 1;
    p_stack(p_count).app_id := p_app_id;
    p_stack(p_count).page_id := p_page_id;

    if p_count > c_max_depth
    then
      l_keep_from := p_count - c_max_depth + 1;
      for i in l_keep_from .. p_count
      loop
        p_stack(i - l_keep_from + 1) := p_stack(i);
      end loop;
      p_count := c_max_depth;
    end if;
  end append_frame;

  procedure parse_stack(
    p_stack in varchar2,
    p_out   in out nocopy t_stack,
    p_count in out nocopy pls_integer
  )
  is
    l_source varchar2(32767 char) := current_stack_value(p_stack);
    l_pair varchar2(128 char);
    l_app_id number;
    l_page_id number;
    l_index pls_integer := 1;
  begin
    p_out.delete;
    p_count := 0;

    if l_source is null
    then
      return;
    end if;

    if not regexp_like(l_source, '^[0-9]{1,10}\.[0-9]{1,10}(~[0-9]{1,10}\.[0-9]{1,10})*$')
    then
      return;
    end if;

    loop
      l_pair := regexp_substr(l_source, '[^~]+', 1, l_index);
      exit when l_pair is null;

      l_app_id := to_number(regexp_substr(l_pair, '^[0-9]+'));
      l_page_id := to_number(regexp_substr(l_pair, '[0-9]+$', 1, 1));
      append_frame(p_out, p_count, l_app_id, l_page_id);
      l_index := l_index + 1;
    end loop;
  exception
    when others then
      p_out.delete;
      p_count := 0;
  end parse_stack;

  function stack_to_string(
    p_stack in t_stack,
    p_count in pls_integer
  ) return varchar2
  is
    l_stack varchar2(32767 char);
  begin
    for i in 1 .. p_count
    loop
      l_stack := l_stack
                 || case when i > 1 then '~' end
                 || to_char(p_stack(i).app_id)
                 || '.'
                 || to_char(p_stack(i).page_id);
    end loop;

    return l_stack;
  end stack_to_string;

  function frame_label(
    p_app_id  in number,
    p_page_id in number
  ) return varchar2
  is
    l_label varchar2(255 char);
  begin
    if p_app_id = c_admin_app_id
    then
      return 'Orac Admin';
    end if;

    if p_app_id = c_plugin_app_id and p_page_id = 1
    then
      return 'Plugin Operations';
    end if;

    if p_app_id = c_plugin_app_id and p_page_id = 2
    then
      return 'Plugin Navigation';
    end if;

    select coalesce(menu.card_title, menu.label, menu.app_alias)
      into l_label
      from orac_code.plugin_apex_app_menu_v menu
     where menu.installed_app_id = p_app_id
       and rownum = 1;

    return l_label;
  exception
    when others then
      return null;
  end frame_label;

  function build_url(
    p_target_app_id  in number,
    p_target_page_id in number,
    p_request        in varchar2,
    p_clear_cache    in varchar2,
    p_stack          in varchar2
  ) return varchar2
  is
    l_item_values varchar2(32767 char);
  begin
    if not is_valid_frame(p_target_app_id, p_target_page_id)
    then
      return null;
    end if;

    l_item_values := p_stack;

    return apex_util.prepare_url(
      p_url           => 'f?p='
                         || to_char(p_target_app_id)
                         || ':'
                         || to_char(p_target_page_id)
                         || ':'
                         || v('APP_SESSION')
                         || ':'
                         || p_request
                         || ':'
                         || v('DEBUG')
                         || ':'
                         || p_clear_cache
                         || ':'
                         || c_stack_item_name
                         || ':'
                         || l_item_values,
      p_checksum_type => 'SESSION'
    );
  end build_url;

  function normalize_stack(
    p_stack in varchar2 default null
  ) return varchar2
  is
    l_stack t_stack;
    l_count pls_integer;
  begin
    parse_stack(p_stack, l_stack, l_count);
    return stack_to_string(l_stack, l_count);
  end normalize_stack;

  function launch_url(
    p_target_app_id  in number,
    p_target_page_id in number,
    p_request        in varchar2 default null,
    p_clear_cache    in varchar2 default null
  ) return varchar2
  is
    l_stack t_stack;
    l_count pls_integer;
    l_app_id number;
    l_page_id number;
  begin
    parse_stack(null, l_stack, l_count);
    l_app_id := to_number(v('APP_ID'));
    l_page_id := to_number(v('APP_PAGE_ID'));

    if l_app_id != p_target_app_id or l_page_id != p_target_page_id
    then
      append_frame(l_stack, l_count, l_app_id, l_page_id);
    end if;

    return build_url(
      p_target_app_id  => p_target_app_id,
      p_target_page_id => p_target_page_id,
      p_request        => p_request,
      p_clear_cache    => p_clear_cache,
      p_stack          => stack_to_string(l_stack, l_count)
    );
  exception
    when others then
      return null;
  end launch_url;

  function return_depth(
    p_stack in varchar2 default null
  ) return number
  is
    l_stack t_stack;
    l_count pls_integer;
  begin
    parse_stack(p_stack, l_stack, l_count);
    return l_count;
  end return_depth;

  function return_label(
    p_position in pls_integer,
    p_stack    in varchar2 default null
  ) return varchar2
  is
    l_stack t_stack;
    l_count pls_integer;
    l_index pls_integer;
  begin
    parse_stack(p_stack, l_stack, l_count);
    l_index := l_count - p_position + 1;

    if l_index < 1 or l_index > l_count
    then
      return null;
    end if;

    return frame_label(l_stack(l_index).app_id, l_stack(l_index).page_id);
  end return_label;

  function return_url(
    p_position in pls_integer,
    p_stack    in varchar2 default null
  ) return varchar2
  is
    l_stack t_stack;
    l_count pls_integer;
    l_index pls_integer;
    l_remaining_count pls_integer;
  begin
    parse_stack(p_stack, l_stack, l_count);
    l_index := l_count - p_position + 1;

    if l_index < 1 or l_index > l_count
    then
      return null;
    end if;

    l_remaining_count := l_index - 1;

    return build_url(
      p_target_app_id  => l_stack(l_index).app_id,
      p_target_page_id => l_stack(l_index).page_id,
      p_request        => null,
      p_clear_cache    => 'RP',
      p_stack          => stack_to_string(l_stack, l_remaining_count)
    );
  exception
    when others then
      return null;
  end return_url;
end apex_return_nav_api;
/

--rollback drop package body orac_code.apex_return_nav_api;
