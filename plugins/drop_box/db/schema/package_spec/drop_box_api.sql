--liquibase formatted sql

--changeset clive:drop_box_package_spec_drop_box_api context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
create or replace package orac_dropbox.drop_box_api as

  function observation_exists(
    p_drop_location_id  in orac_dropbox.drop_job.drop_location_id%type,
    p_source_path       in orac_dropbox.drop_job.source_path%type,
    p_source_size_bytes in orac_dropbox.drop_job.source_size_bytes%type,
    p_source_mtime      in orac_dropbox.drop_job.source_mtime%type
  ) return number;

  procedure enqueue_job(
    p_drop_location_id  in orac_dropbox.drop_job.drop_location_id%type,
    p_source_path       in orac_dropbox.drop_job.source_path%type,
    p_source_filename   in orac_dropbox.drop_job.source_filename%type,
    p_source_size_bytes in orac_dropbox.drop_job.source_size_bytes%type,
    p_source_mtime      in orac_dropbox.drop_job.source_mtime%type,
    p_stable_on         in orac_dropbox.drop_job.stable_on%type,
    p_source_hash       in orac_dropbox.drop_job.source_hash%type
  );

  procedure update_status(
    p_drop_job_id   in orac_dropbox.drop_job.drop_job_id%type,
    p_status_code   in orac_dropbox.drop_job.status_code%type,
    p_error_message in orac_dropbox.drop_job.error_message%type default null,
    p_document_id   in orac_dropbox.drop_job.document_id%type default null
  );

end drop_box_api;
/
