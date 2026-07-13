--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_knowledge_ingestion_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_code.knowledge_ingestion_api
authid definer
as
  function submit_managed_file(
    p_source_type              in varchar2,
    p_source_reference         in varchar2,
    p_parent_source_reference  in varchar2,
    p_content_sha256           in varchar2,
    p_content_uri              in varchar2,
    p_mime_type                in varchar2,
    p_original_filename        in varchar2,
    p_byte_size                in number,
    p_target_scope_type        in varchar2,
    p_target_scope_key         in varchar2,
    p_processing_profile_code  in varchar2 default null,
    p_processing_instruction   in clob default null,
    p_source_modified_on       in timestamp with time zone default null
  ) return number;

  function try_claim_next_request(
    p_owner_id      in varchar2,
    p_lease_seconds in number default 300
  ) return number;

  procedure mark_stage(
    p_ingestion_request_id in number,
    p_owner_id             in varchar2,
    p_lease_token          in varchar2,
    p_status_code          in varchar2,
    p_stage_code           in varchar2
  );

  function ensure_document_version(
    p_ingestion_request_id in number,
    p_title                in varchar2 default null,
    p_source_modified_on   in timestamp with time zone default null
  ) return number;

  function create_extraction(
    p_document_version_id in number,
    p_extractor_code      in varchar2,
    p_extractor_version   in varchar2,
    p_extracted_text      in clob,
    p_text_sha256         in varchar2
  ) return number;

  function create_chunk_set(
    p_extraction_id      in number,
    p_chunker_code       in varchar2,
    p_chunker_version    in varchar2,
    p_chunk_size_tokens  in number,
    p_overlap_tokens     in number
  ) return number;

  function insert_chunk(
    p_chunk_set_id    in number,
    p_chunk_no        in number,
    p_span_start      in number,
    p_span_end        in number,
    p_chunk_text      in clob,
    p_token_count     in number,
    p_content_sha256  in varchar2
  ) return number;

  function upsert_embedding_model(
    p_provider_code    in varchar2,
    p_model_name       in varchar2,
    p_model_revision   in varchar2,
    p_dimensions       in number,
    p_distance_metric  in varchar2 default 'COSINE',
    p_normalisation    in varchar2 default 'UNIT'
  ) return number;

  function insert_chunk_embedding(
    p_chunk_id              in number,
    p_embedding_model_id    in number,
    p_embedding_vector      in clob,
    p_embedding_text_sha256 in varchar2
  ) return number;

  procedure complete_request(
    p_ingestion_request_id in number,
    p_owner_id             in varchar2,
    p_lease_token          in varchar2
  );

  procedure fail_request(
    p_ingestion_request_id in number,
    p_owner_id             in varchar2,
    p_lease_token          in varchar2,
    p_error_code           in varchar2,
    p_error_message        in clob,
    p_retryable_yn         in varchar2 default 'Y'
  );
end knowledge_ingestion_api;
/

--rollback drop package orac_code.knowledge_ingestion_api;
