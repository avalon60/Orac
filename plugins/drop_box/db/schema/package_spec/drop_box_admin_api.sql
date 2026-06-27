--liquibase formatted sql

--changeset clive:create_package_spec_orac_dropbox_package_spec_drop_box_admin_api context:plugin,prod labels:plugin,drop_box stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-06-27
-- __description__: controlled admin API for drop-box location configuration

create or replace package orac_dropbox.drop_box_admin_api as

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
  );

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
  );

  procedure set_enabled(
    p_drop_location_id in orac_dropbox.drop_location.drop_location_id%type,
    p_enabled_yn       in orac_dropbox.drop_location.enabled_yn%type,
    p_row_version      in orac_dropbox.drop_location.row_version%type
  );

end drop_box_admin_api;
/

--rollback drop package orac_dropbox.drop_box_admin_api;
