--liquibase formatted sql

--changeset clive:seed_orac_dropbox_seed_data_drop_location_examples context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-06-27
-- __description__: disabled example drop-box locations for admin configuration guidance

merge into orac_dropbox.drop_location dst
using (
  select 'HA_CONCLUSIONS' location_code,
         'Home Assistant Conclusions' display_name,
         '/__orac_dropbox_examples__/home_assistant_conclusions' path,
         'plugin' target_scope_type,
         'home_assistant' target_scope_key,
         'concise_knowledge_note' processing_profile,
         'Example only. Edit the path and enable after mounting the real Home Assistant conclusions drop directory.' processing_instruction
    from dual
  union all
  select 'ORAC_ARCHITECTURE_NOTES' location_code,
         'Orac Architecture Notes' display_name,
         '/__orac_dropbox_examples__/orac_architecture_notes' path,
         'project' target_scope_type,
         'ORAC_CORE' target_scope_key,
         'implementation_decision_record' processing_profile,
         'Example only. Edit the path and enable after choosing the project notes drop directory.' processing_instruction
    from dual
) src
on (dst.location_code = src.location_code)
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

--rollback delete from orac_dropbox.drop_location where location_code in ('HA_CONCLUSIONS', 'ORAC_ARCHITECTURE_NOTES') and enabled_yn = 'N';
