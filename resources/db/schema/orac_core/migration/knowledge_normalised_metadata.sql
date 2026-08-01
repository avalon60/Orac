--liquibase formatted sql

--changeset clive:add_knowledge_normalised_metadata context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner='ORAC_CORE' and table_name='KNOWLEDGE_EXTRACTIONS' and column_name='OUTPUT_MIME_TYPE';
alter table orac_core.knowledge_document_versions add (source_format_code varchar2(50 char));
alter table orac_core.knowledge_extractions add (
  output_mime_type varchar2(255 char),
  extractor_metadata_json json
);
alter table orac_core.knowledge_chunks add (chunk_metadata_json json);
--rollback alter table orac_core.knowledge_chunks drop column chunk_metadata_json; alter table orac_core.knowledge_extractions drop (output_mime_type, extractor_metadata_json); alter table orac_core.knowledge_document_versions drop column source_format_code;
