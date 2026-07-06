--liquibase formatted sql

--changeset clive:seed_orac_dropbox_seed_data_drop_location_examples context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-06-27
-- __description__: disabled example drop-box locations for admin configuration guidance

delete from orac_dropbox.drop_location
 where location_code = 'HA_CONCLUSIONS'
   and enabled_yn = 'N'
   and target_scope_type = 'plugin'
   and target_scope_key = 'home_assistant'
   and path in (
         '/__orac_dropbox_examples__/home_assistant_conclusions',
         '/tmp/orac-dropbox-examples/home_assistant_conclusions'
       )
   and processing_instruction like 'Example only.%';

merge into orac_dropbox.drop_location dst
using (
  select 'ORAC_ARCHITECTURE_NOTES' location_code,
         'Orac Architecture Notes' display_name,
         '/tmp/orac-dropbox-examples/orac_architecture_notes' path,
         'project' target_scope_type,
         'ORAC_CORE' target_scope_key,
         'implementation_decision_record' processing_profile,
         'Example only. Edit the path and enable after choosing the project notes drop directory.' processing_instruction
    from dual
) src
on (dst.location_code = src.location_code)
when matched then
  update set
    dst.display_name           = src.display_name,
    dst.path                   = src.path,
    dst.target_scope_type      = src.target_scope_type,
    dst.target_scope_key       = src.target_scope_key,
    dst.processing_profile     = src.processing_profile,
    dst.processing_instruction = src.processing_instruction,
    dst.allowed_extensions     = 'md,txt,pdf',
    dst.ignore_patterns        = '*.tmp,*.part,*.partial,*.crdownload,.~*,~$*,.DS_Store',
    dst.recursive_yn           = 'N',
    dst.move_processed_yn      = 'N',
    dst.processed_path         = null,
    dst.failed_path            = null,
    dst.max_file_size_mb       = 100,
    dst.stability_seconds      = 10
  where dst.enabled_yn = 'N'
when not matched then
  insert (
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
    src.location_code,
    src.display_name,
    src.path,
    'N',
    src.target_scope_type,
    src.target_scope_key,
    src.processing_profile,
    src.processing_instruction,
    'md,txt,pdf',
    '*.tmp,*.part,*.partial,*.crdownload,.~*,~$*,.DS_Store',
    'N',
    'N',
    null,
    null,
    100,
    10
  );

--rollback delete from orac_dropbox.drop_location where location_code in ('ORAC_ARCHITECTURE_NOTES') and enabled_yn = 'N';
