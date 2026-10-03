--liquibase formatted sql

--changeset clive:drop_box_comment_drop_job context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
comment on column orac_dropbox.drop_job.producer_knowledge_scope_id is 'Immutable Drop Box producer scope at enqueue; distinguishes reused private job numbers after reinstall without changing project-scoped source deduplication.';
comment on column orac_dropbox.drop_job.target_knowledge_scope_id is 'Immutable snapshot of the location target scope at enqueue. Core validates this exact ID before acceptance; a reused plugin name cannot redirect queued work.';
comment on table orac_dropbox.drop_job is 'Durable source-file ingestion jobs created by the drop-box plugin.'
;
comment on column orac_dropbox.drop_job.effective_processing_profile is 'Processing profile code copied from drop_location when the job was enqueued.'
;
comment on column orac_dropbox.drop_job.effective_profile_instruction is 'Processing profile default instruction copied from drop_processing_profile when the job was enqueued.'
;
comment on column orac_dropbox.drop_job.effective_instruction is 'Processing instruction copied from drop_location when the job was enqueued.'
;
comment on column orac_dropbox.drop_job.knowledge_ingestion_request_id is 'Loose Core knowledge ingestion request correlation id. This is deliberately not physically foreign-keyed to ORAC_CORE because plugin schemas must not depend directly on Core tables.'
;
