--liquibase formatted sql

--changeset clive:drop_box_view_drop_job_handoff_v context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
create or replace force view orac_dropbox.drop_job_handoff_v as
select job.drop_job_id,
       job.drop_location_id,
       loc.location_code,
       loc.path as location_root,
       job.source_path,
       job.source_filename,
       job.source_hash,
       job.source_size_bytes,
       job.source_mtime,
       job.detected_on,
       job.stable_on,
       job.status_code,
       job.effective_scope_type,
       job.effective_scope_key,
       job.effective_processing_profile,
       job.effective_profile_instruction,
       job.effective_instruction,
       job.document_id,
       job.knowledge_ingestion_request_id,
       job.created_on
  from orac_dropbox.drop_job job
  join orac_dropbox.drop_location loc
    on loc.drop_location_id = job.drop_location_id
 where job.status_code = 'queued';
/
