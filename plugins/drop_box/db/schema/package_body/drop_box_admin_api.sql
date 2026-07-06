--liquibase formatted sql

--changeset clive:create_package_body_orac_dropbox_package_body_drop_box_admin_api context:plugin,prod labels:plugin,drop_box stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-27
-- __description__: implements controlled admin writes for drop-box locations

create or replace package body orac_dropbox.drop_box_admin_api as

  procedure assert_yn(
    p_value in varchar2,
    p_name  in varchar2
  )
  is
  begin
    if upper(coalesce(p_value, '?')) not in ('Y', 'N')
    then
      raise_application_error(-20001, p_name || ' must be Y or N.');
    end if;
  end assert_yn;

  procedure validate_location(
    p_drop_location_id   in orac_dropbox.drop_location.drop_location_id%type,
    p_location_code      in orac_dropbox.drop_location.location_code%type,
    p_display_name       in orac_dropbox.drop_location.display_name%type,
    p_path               in orac_dropbox.drop_location.path%type,
    p_enabled_yn         in orac_dropbox.drop_location.enabled_yn%type,
    p_target_scope_type  in orac_dropbox.drop_location.target_scope_type%type,
    p_target_scope_key   in orac_dropbox.drop_location.target_scope_key%type,
    p_processing_profile in orac_dropbox.drop_location.processing_profile%type,
    p_recursive_yn       in orac_dropbox.drop_location.recursive_yn%type,
    p_move_processed_yn  in orac_dropbox.drop_location.move_processed_yn%type,
    p_max_file_size_mb   in orac_dropbox.drop_location.max_file_size_mb%type,
    p_stability_seconds  in orac_dropbox.drop_location.stability_seconds%type
  )
  is
    l_duplicate_count number;
    l_profile_count   number;
  begin
    if not regexp_like(coalesce(p_location_code, ' '), '^[A-Z][A-Z0-9_]{1,99}$')
    then
      raise_application_error(
        -20002,
        'Location code must be uppercase letters, digits, and underscores.'
      );
    end if;

    if trim(p_display_name) is null
    then
      raise_application_error(-20003, 'Display name is required.');
    end if;

    assert_yn(p_enabled_yn, 'Enabled flag');
    assert_yn(p_recursive_yn, 'Recursive flag');
    assert_yn(p_move_processed_yn, 'Move processed flag');

    if upper(p_enabled_yn) = 'Y' and trim(p_path) is null
    then
      raise_application_error(-20004, 'Enabled drop locations require a source path.');
    end if;

    if trim(p_path) is not null
       and not regexp_like(trim(p_path), '^/[^[:cntrl:]]+$')
    then
      raise_application_error(-20005, 'Source path must be an absolute filesystem path.');
    end if;

    if lower(coalesce(p_target_scope_type, ' ')) not in ('plugin', 'project')
    then
      raise_application_error(-20006, 'Target scope type must be plugin or project.');
    end if;

    if trim(p_target_scope_key) is null
    then
      raise_application_error(-20007, 'Target scope key is required.');
    end if;

    if not regexp_like(coalesce(p_processing_profile, ' '), '^[a-z][a-z0-9_]{1,99}$')
    then
      raise_application_error(
        -20008,
        'Processing profile must be a lowercase profile code.'
      );
    end if;

    select count(*)
      into l_profile_count
      from orac_dropbox.drop_processing_profile prf
     where prf.profile_code = lower(trim(p_processing_profile))
       and prf.active_yn = 'Y';

    if l_profile_count = 0
    then
      raise_application_error(-20013, 'Processing profile is unknown or inactive.');
    end if;

    if p_stability_seconds is null or p_stability_seconds < 1
    then
      raise_application_error(-20009, 'Stability interval must be at least 1 second.');
    end if;

    if p_max_file_size_mb is not null and p_max_file_size_mb <= 0
    then
      raise_application_error(-20010, 'Maximum file size must be greater than zero.');
    end if;

    if upper(p_enabled_yn) = 'Y' and trim(p_path) is not null
    then
      select count(*)
        into l_duplicate_count
        from orac_dropbox.drop_location loc
       where loc.enabled_yn = 'Y'
         and regexp_replace(trim(loc.path), '/+$', '') =
             regexp_replace(trim(p_path), '/+$', '')
         and (p_drop_location_id is null or loc.drop_location_id <> p_drop_location_id);

      if l_duplicate_count > 0
      then
        raise_application_error(-20011, 'Duplicate active source paths are not allowed.');
      end if;
    end if;
  end validate_location;

  procedure create_location(
    p_location_code          in orac_dropbox.drop_location.location_code%type,
    p_display_name           in orac_dropbox.drop_location.display_name%type,
    p_path                   in orac_dropbox.drop_location.path%type,
    p_enabled_yn             in orac_dropbox.drop_location.enabled_yn%type,
    p_target_scope_type      in orac_dropbox.drop_location.target_scope_type%type,
    p_target_scope_key       in orac_dropbox.drop_location.target_scope_key%type,
    p_processing_profile     in orac_dropbox.drop_location.processing_profile%type,
    p_processing_instruction in orac_dropbox.drop_location.processing_instruction%type,
    p_allowed_extensions     in orac_dropbox.drop_location.allowed_extensions%type,
    p_ignore_patterns        in orac_dropbox.drop_location.ignore_patterns%type,
    p_recursive_yn           in orac_dropbox.drop_location.recursive_yn%type,
    p_move_processed_yn      in orac_dropbox.drop_location.move_processed_yn%type,
    p_processed_path         in orac_dropbox.drop_location.processed_path%type,
    p_failed_path            in orac_dropbox.drop_location.failed_path%type,
    p_max_file_size_mb       in orac_dropbox.drop_location.max_file_size_mb%type,
    p_stability_seconds      in orac_dropbox.drop_location.stability_seconds%type,
    p_drop_location_id       out orac_dropbox.drop_location.drop_location_id%type
  )
  is
  begin
    validate_location(
      p_drop_location_id   => null,
      p_location_code      => p_location_code,
      p_display_name       => p_display_name,
      p_path               => p_path,
      p_enabled_yn         => p_enabled_yn,
      p_target_scope_type  => p_target_scope_type,
      p_target_scope_key   => p_target_scope_key,
      p_processing_profile => p_processing_profile,
      p_recursive_yn       => p_recursive_yn,
      p_move_processed_yn  => p_move_processed_yn,
      p_max_file_size_mb   => p_max_file_size_mb,
      p_stability_seconds  => p_stability_seconds
    );

    insert into orac_dropbox.drop_location (
      location_code,
      display_name,
      path,
      enabled_yn,
      target_scope_type,
      target_scope_key,
      processing_profile,
      processing_instruction,
      allowed_extensions,
      ignore_patterns,
      recursive_yn,
      move_processed_yn,
      processed_path,
      failed_path,
      max_file_size_mb,
      stability_seconds
    ) values (
      upper(trim(p_location_code)),
      trim(p_display_name),
      trim(p_path),
      upper(p_enabled_yn),
      lower(trim(p_target_scope_type)),
      trim(p_target_scope_key),
      lower(trim(p_processing_profile)),
      p_processing_instruction,
      trim(p_allowed_extensions),
      trim(p_ignore_patterns),
      upper(p_recursive_yn),
      upper(p_move_processed_yn),
      trim(p_processed_path),
      trim(p_failed_path),
      p_max_file_size_mb,
      p_stability_seconds
    )
    returning drop_location_id into p_drop_location_id;
  end create_location;

  procedure update_location(
    p_drop_location_id       in orac_dropbox.drop_location.drop_location_id%type,
    p_location_code          in orac_dropbox.drop_location.location_code%type,
    p_display_name           in orac_dropbox.drop_location.display_name%type,
    p_path                   in orac_dropbox.drop_location.path%type,
    p_enabled_yn             in orac_dropbox.drop_location.enabled_yn%type,
    p_target_scope_type      in orac_dropbox.drop_location.target_scope_type%type,
    p_target_scope_key       in orac_dropbox.drop_location.target_scope_key%type,
    p_processing_profile     in orac_dropbox.drop_location.processing_profile%type,
    p_processing_instruction in orac_dropbox.drop_location.processing_instruction%type,
    p_allowed_extensions     in orac_dropbox.drop_location.allowed_extensions%type,
    p_ignore_patterns        in orac_dropbox.drop_location.ignore_patterns%type,
    p_recursive_yn           in orac_dropbox.drop_location.recursive_yn%type,
    p_move_processed_yn      in orac_dropbox.drop_location.move_processed_yn%type,
    p_processed_path         in orac_dropbox.drop_location.processed_path%type,
    p_failed_path            in orac_dropbox.drop_location.failed_path%type,
    p_max_file_size_mb       in orac_dropbox.drop_location.max_file_size_mb%type,
    p_stability_seconds      in orac_dropbox.drop_location.stability_seconds%type,
    p_row_version            in orac_dropbox.drop_location.row_version%type
  )
  is
  begin
    validate_location(
      p_drop_location_id   => p_drop_location_id,
      p_location_code      => p_location_code,
      p_display_name       => p_display_name,
      p_path               => p_path,
      p_enabled_yn         => p_enabled_yn,
      p_target_scope_type  => p_target_scope_type,
      p_target_scope_key   => p_target_scope_key,
      p_processing_profile => p_processing_profile,
      p_recursive_yn       => p_recursive_yn,
      p_move_processed_yn  => p_move_processed_yn,
      p_max_file_size_mb   => p_max_file_size_mb,
      p_stability_seconds  => p_stability_seconds
    );

    update orac_dropbox.drop_location
       set location_code          = upper(trim(p_location_code)),
           display_name           = trim(p_display_name),
           path                   = trim(p_path),
           enabled_yn             = upper(p_enabled_yn),
           target_scope_type      = lower(trim(p_target_scope_type)),
           target_scope_key       = trim(p_target_scope_key),
           processing_profile     = lower(trim(p_processing_profile)),
           processing_instruction = p_processing_instruction,
           allowed_extensions     = trim(p_allowed_extensions),
           ignore_patterns        = trim(p_ignore_patterns),
           recursive_yn           = upper(p_recursive_yn),
           move_processed_yn      = upper(p_move_processed_yn),
           processed_path         = trim(p_processed_path),
           failed_path            = trim(p_failed_path),
           max_file_size_mb       = p_max_file_size_mb,
           stability_seconds      = p_stability_seconds,
           updated_on             = systimestamp,
           updated_by             = coalesce(
                                      sys_context('userenv', 'client_identifier'),
                                      sys_context('userenv', 'proxy_user'),
                                      sys_context('userenv', 'session_user'),
                                      user
                                    ),
           row_version            = row_version + 1
     where drop_location_id = p_drop_location_id
       and row_version = p_row_version;

    if sql%rowcount = 0
    then
      raise_application_error(-20012, 'Drop location was not found or has changed.');
    end if;
  end update_location;

  procedure set_enabled(
    p_drop_location_id in orac_dropbox.drop_location.drop_location_id%type,
    p_enabled_yn       in orac_dropbox.drop_location.enabled_yn%type,
    p_row_version      in orac_dropbox.drop_location.row_version%type
  )
  is
    l_row orac_dropbox.drop_location%rowtype;
  begin
    assert_yn(p_enabled_yn, 'Enabled flag');

    select *
      into l_row
      from orac_dropbox.drop_location
     where drop_location_id = p_drop_location_id;

    validate_location(
      p_drop_location_id   => l_row.drop_location_id,
      p_location_code      => l_row.location_code,
      p_display_name       => l_row.display_name,
      p_path               => l_row.path,
      p_enabled_yn         => p_enabled_yn,
      p_target_scope_type  => l_row.target_scope_type,
      p_target_scope_key   => l_row.target_scope_key,
      p_processing_profile => l_row.processing_profile,
      p_recursive_yn       => l_row.recursive_yn,
      p_move_processed_yn  => l_row.move_processed_yn,
      p_max_file_size_mb   => l_row.max_file_size_mb,
      p_stability_seconds  => l_row.stability_seconds
    );

    update orac_dropbox.drop_location
       set enabled_yn  = upper(p_enabled_yn),
           updated_on  = systimestamp,
           updated_by  = coalesce(
                           sys_context('userenv', 'client_identifier'),
                           sys_context('userenv', 'proxy_user'),
                           sys_context('userenv', 'session_user'),
                           user
                         ),
           row_version = row_version + 1
     where drop_location_id = p_drop_location_id
       and row_version = p_row_version;

    if sql%rowcount = 0
    then
      raise_application_error(-20012, 'Drop location was not found or has changed.');
    end if;
  exception
    when no_data_found then
      raise_application_error(-20013, 'Drop location was not found.');
  end set_enabled;

  procedure delete_location(
    p_drop_location_id in orac_dropbox.drop_location.drop_location_id%type,
    p_row_version      in orac_dropbox.drop_location.row_version%type
  )
  is
    e_child_record_found exception;
    pragma exception_init(e_child_record_found, -2292);
    l_job_count number;
  begin
    select count(*)
      into l_job_count
      from orac_dropbox.drop_job job
     where job.drop_location_id = p_drop_location_id;

    if l_job_count > 0
    then
      raise_application_error(
        -20014,
        'Drop location has job history and cannot be deleted. Disable it instead.'
      );
    end if;

    delete from orac_dropbox.drop_location
     where drop_location_id = p_drop_location_id
       and row_version = p_row_version;

    if sql%rowcount = 0
    then
      raise_application_error(-20012, 'Drop location was not found or has changed.');
    end if;
  exception
    when e_child_record_found then
      raise_application_error(
        -20014,
        'Drop location has job history and cannot be deleted. Disable it instead.'
      );
  end delete_location;

end drop_box_admin_api;
/

--rollback drop package body orac_dropbox.drop_box_admin_api;
