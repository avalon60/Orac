--liquibase formatted sql

--changeset clive:create_view_orac_dropbox_view_drop_job_event_admin_v context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-06-27
-- __description__: admin projection of drop-box ingestion job audit events

create or replace view orac_dropbox.drop_job_event_admin_v as
select evt.drop_job_event_id,
       evt.drop_job_id,
       job.drop_location_id,
       loc.location_code,
       loc.display_name location_display_name,
       job.source_path,
       job.source_filename,
       evt.event_ts,
       evt.event_type,
       case evt.event_type
         when 'queued'
         then 'Drop-box source file queued for ingestion handoff.'
         when 'processing'
         then 'Drop Box processing started.'
         when 'handed_off'
         then 'Core accepted a managed-file ingestion request.'
         when 'completed'
         then 'Drop Box processing completed.'
         when 'failed'
         then 'Drop Box processing failed; review restricted logs.'
         when 'quarantined'
         then 'Drop Box job was quarantined; review restricted logs.'
         when 'repair_requeued_core_handoff'
         then 'Drop Box job was requeued after Core handoff became available.'
         else 'Drop Box job event recorded; review restricted logs for details.'
       end event_message_redacted,
       evt.created_on,
       evt.created_by
  from orac_dropbox.drop_job_event evt
  join orac_dropbox.drop_job job
    on job.drop_job_id = evt.drop_job_id
  join orac_dropbox.drop_location loc
    on loc.drop_location_id = job.drop_location_id;

--rollback drop view orac_dropbox.drop_job_event_admin_v;
