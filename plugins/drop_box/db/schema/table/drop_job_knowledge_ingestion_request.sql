--liquibase formatted sql

--changeset clive:drop_box_table_drop_job_knowledge_ingestion_request context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_JOB' and column_name = 'KNOWLEDGE_INGESTION_REQUEST_ID'
alter table orac_dropbox.drop_job add (
  knowledge_ingestion_request_id number
);

--rollback alter table orac_dropbox.drop_job drop column knowledge_ingestion_request_id;
