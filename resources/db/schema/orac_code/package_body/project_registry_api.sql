--liquibase formatted sql

--changeset clive:create_package_body_orac_code_project_registry_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-07-11
-- __description__: controlled project registry maintenance API body

create or replace package body orac_code.project_registry_api as
  function normalised_code(
    p_project_code in orac_api.project_registry_v.project_code%type,
    p_required     in boolean default true
  ) return orac_api.project_registry_v.project_code%type
  is
    l_project_code orac_api.project_registry_v.project_code%type;
  begin
    l_project_code := upper(trim(p_project_code));

    if p_required
       and l_project_code is null
    then
      raise_application_error(-20030, 'Project code is required.');
    end if;

    if l_project_code is not null
       and not regexp_like(l_project_code, '^[A-Z][A-Z0-9_]{1,99}$')
    then
      raise_application_error(
        -20031,
        'Project code must start with an uppercase letter and contain only uppercase letters, digits, and underscores.'
      );
    end if;

    return l_project_code;
  end normalised_code;

  function normalised_active_yn(
    p_active_yn in orac_api.project_registry_v.active_yn%type
  ) return orac_api.project_registry_v.active_yn%type
  is
    l_active_yn orac_api.project_registry_v.active_yn%type;
  begin
    l_active_yn := upper(trim(coalesce(p_active_yn, 'Y')));

    if l_active_yn not in ('Y', 'N')
    then
      raise_application_error(-20032, 'Project active flag must be Y or N.');
    end if;

    return l_active_yn;
  end normalised_active_yn;

  function row_checksum(
    p_row in orac_api.project_registry_v%rowtype
  ) return varchar2
  is
    l_checksum varchar2(64 char);
  begin
    select standard_hash(
             p_row.project_id
             || ':' || p_row.project_code
             || ':' || p_row.display_name
             || ':' || nvl(p_row.description, chr(0))
             || ':' || p_row.active_yn
             || ':' || p_row.row_version,
             'SHA256'
           )
      into l_checksum
      from dual;

    return l_checksum;
  end row_checksum;

  procedure assert_display_name(
    p_display_name in orac_api.project_registry_v.display_name%type
  )
  is
  begin
    if trim(p_display_name) is null
    then
      raise_application_error(-20033, 'Project display name is required.');
    end if;
  end assert_display_name;

  procedure load_existing(
    p_project_id   in  orac_api.project_registry_v.project_id%type,
    p_row_checksum in  varchar2,
    p_row          out orac_api.project_registry_v%rowtype
  )
  is
  begin
    begin
      select *
        into p_row
        from orac_api.project_registry_v
       where project_id = p_project_id;
    exception
      when no_data_found then
        raise_application_error(
          -20034,
          'Project was changed by another session. Refresh and try again.'
        );
    end;

    if row_checksum(p_row) <> p_row_checksum
    then
      raise_application_error(
        -20034,
        'Project was changed by another session. Refresh and try again.'
      );
    end if;
  end load_existing;

  procedure create_project(
    p_project_code in orac_api.project_registry_v.project_code%type,
    p_display_name in orac_api.project_registry_v.display_name%type,
    p_description  in orac_api.project_registry_v.description%type default null,
    p_active_yn    in orac_api.project_registry_v.active_yn%type default 'Y'
  )
  is
    l_row orac_api.project_registry_v%rowtype;
  begin
    l_row.project_code := normalised_code(p_project_code);
    assert_display_name(p_display_name);

    l_row.display_name := trim(p_display_name);
    l_row.description := trim(p_description);
    l_row.active_yn := normalised_active_yn(p_active_yn);

    orac_api.project_registry_tapi.ins(l_row);
    orac_code.knowledge_scope_api.synchronise_project_scope(l_row.project_id);
  exception
    when dup_val_on_index then
      raise_application_error(-20035, 'Project code already exists.');
  end create_project;

  procedure update_project(
    p_project_id   in orac_api.project_registry_v.project_id%type,
    p_project_code in orac_api.project_registry_v.project_code%type,
    p_display_name in orac_api.project_registry_v.display_name%type,
    p_description  in orac_api.project_registry_v.description%type default null,
    p_active_yn    in orac_api.project_registry_v.active_yn%type default 'Y',
    p_row_checksum in varchar2
  )
  is
    l_project_code orac_api.project_registry_v.project_code%type;
    l_row          orac_api.project_registry_v%rowtype;
  begin
    l_project_code := normalised_code(p_project_code);
    assert_display_name(p_display_name);
    load_existing(p_project_id, p_row_checksum, l_row);

    if l_row.project_code <> l_project_code
    then
      raise_application_error(-20036, 'Project code cannot be changed.');
    end if;

    l_row.display_name := trim(p_display_name);
    l_row.description := trim(p_description);
    l_row.active_yn := normalised_active_yn(p_active_yn);

    begin
      orac_api.project_registry_tapi.upd(
        p_project_id  => l_row.project_id,
        p_row         => l_row,
        p_row_version => l_row.row_version
      );
    exception
      when no_data_found then
        raise_application_error(
          -20034,
          'Project was changed by another session. Refresh and try again.'
        );
    end;
  end update_project;

  procedure deactivate_project(
    p_project_id   in orac_api.project_registry_v.project_id%type,
    p_row_checksum in varchar2
  )
  is
    l_row orac_api.project_registry_v%rowtype;
  begin
    load_existing(p_project_id, p_row_checksum, l_row);
    l_row.active_yn := 'N';

    begin
      orac_api.project_registry_tapi.upd(
        p_project_id  => l_row.project_id,
        p_row         => l_row,
        p_row_version => l_row.row_version
      );
    exception
      when no_data_found then
        raise_application_error(
          -20034,
          'Project was changed by another session. Refresh and try again.'
        );
    end;
  end deactivate_project;

  procedure upsert_project(
    p_project_code in orac_api.project_registry_v.project_code%type,
    p_display_name in orac_api.project_registry_v.display_name%type,
    p_description  in orac_api.project_registry_v.description%type default null,
    p_active_yn    in orac_api.project_registry_v.active_yn%type default 'Y'
  )
  is
    l_project_id   orac_api.project_registry_v.project_id%type;
    l_project_code orac_api.project_registry_v.project_code%type;
    l_row_checksum varchar2(64);
  begin
    l_project_code := normalised_code(p_project_code);

    begin
      select project_id,
             row_checksum
        into l_project_id,
             l_row_checksum
        from orac_code.project_registry_v
       where project_code = l_project_code;
    exception
      when no_data_found then
        create_project(
          p_project_code => l_project_code,
          p_display_name => p_display_name,
          p_description  => p_description,
          p_active_yn    => p_active_yn
        );
        return;
    end;

    update_project(
      p_project_id   => l_project_id,
      p_project_code => l_project_code,
      p_display_name => p_display_name,
      p_description  => p_description,
      p_active_yn    => p_active_yn,
      p_row_checksum => l_row_checksum
    );
    orac_code.knowledge_scope_api.synchronise_project_scope(l_project_id);
  end upsert_project;
end project_registry_api;
/

--rollback drop package body orac_code.project_registry_api;
