--liquibase formatted sql

--changeset clive:drop_box_comment_drop_job_event context:plugin,prod labels:plugin,drop_box stripComments:false runOnChange:true
comment on table orac_dropbox.drop_job_event is 'Append-only audit events for drop-box ingestion jobs.'
;
