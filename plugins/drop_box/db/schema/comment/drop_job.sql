comment on table orac_dropbox.drop_job is 'Durable source-file ingestion jobs created by the drop-box plugin.'
;
comment on column orac_dropbox.drop_job.effective_processing_profile is 'Processing profile code copied from drop_location when the job was enqueued.'
;
comment on column orac_dropbox.drop_job.effective_profile_instruction is 'Processing profile default instruction copied from drop_processing_profile when the job was enqueued.'
;
comment on column orac_dropbox.drop_job.effective_instruction is 'Processing instruction copied from drop_location when the job was enqueued.'
;
