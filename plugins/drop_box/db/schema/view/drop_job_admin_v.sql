--liquibase formatted sql

--changeset clive:create_view_orac_dropbox_view_drop_job_admin_v context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-06-27
-- __description__: admin projection of drop-box ingestion jobs

create or replace view orac_dropbox.drop_job_admin_v as
select job.drop_job_id,
       job.drop_location_id,
       loc.location_code,
       loc.display_name location_display_name,
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
       job.target_knowledge_scope_id,
       job.producer_knowledge_scope_id,
       job.effective_processing_profile,
       job.effective_profile_instruction,
       job.effective_instruction,
       job.effective_classification_tags_json,
       job.conversion_attempts,
       job.next_attempt_on,
       job.failure_reason_code,
       job.last_warning_on,
       case
         when job.error_message is null then null
         when job.status_code = 'quarantined'
         then 'Drop Box job was quarantined; review restricted logs.'
         when job.status_code = 'failed'
         then 'Drop Box processing failed; review restricted logs.'
         when job.status_code = 'deferred_prerequisite'
         then 'A document-conversion prerequisite is unavailable.'
         when job.status_code = 'conversion_retry_wait'
         then 'Document conversion is waiting for its next retry.'
         else 'Drop Box reported an error; review restricted logs.'
       end error_summary_redacted,
       job.document_id,
       job.knowledge_ingestion_request_id,
       job.started_on,
       job.completed_on,
       job.created_on,
       job.updated_on,
       job.row_version
  from orac_dropbox.drop_job job
  join orac_dropbox.drop_location loc
    on loc.drop_location_id = job.drop_location_id;

--rollback drop view orac_dropbox.drop_job_admin_v;
