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
       evt.event_message,
       evt.created_on,
       evt.created_by
  from orac_dropbox.drop_job_event evt
  join orac_dropbox.drop_job job
    on job.drop_job_id = evt.drop_job_id
  join orac_dropbox.drop_location loc
    on loc.drop_location_id = job.drop_location_id;

--rollback drop view orac_dropbox.drop_job_event_admin_v;
