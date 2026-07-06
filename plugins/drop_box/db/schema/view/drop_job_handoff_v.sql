--liquibase formatted sql
create or replace force view orac_dropbox.drop_job_handoff_v as
select drop_job_id,
       drop_location_id,
       source_path,
       source_filename,
       source_hash,
       source_size_bytes,
       source_mtime,
       detected_on,
       stable_on,
       status_code,
       effective_scope_type,
       effective_scope_key,
       effective_processing_profile,
       effective_profile_instruction,
       effective_instruction,
       document_id,
       created_on
  from orac_dropbox.drop_job
 where status_code in ('queued', 'failed');
/
