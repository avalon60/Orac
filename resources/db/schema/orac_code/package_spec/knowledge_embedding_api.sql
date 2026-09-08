--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 01-Sep-2026
-- Description: Defines immutable native knowledge embedding lifecycle operations.

--changeset clive:create_package_spec_orac_code_knowledge_embedding_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_code.knowledge_embedding_api
authid definer
as
  function ensure_profile(
    p_profile_version          in varchar2,
    p_provider_code            in varchar2,
    p_model_name               in varchar2,
    p_model_digest             in varchar2,
    p_document_input_prefix    in varchar2,
    p_query_input_prefix       in varchar2,
    p_retrieval_policy_version in varchar2 default 'knowledge-hybrid-v1',
    p_semantic_threshold       in number default 0.60
  ) return number;

  function active_profile_json return clob;

  function begin_reembedding_run(
    p_embedding_profile_id in number
  ) return number;

  procedure open_reembedding_chunks(
    p_reembedding_run_id in number,
    p_chunk_limit        in number,
    p_content_rows       out sys_refcursor
  );

  function store_native_embedding(
    p_embedding_profile_id  in number,
    p_chunk_id              in number,
    p_embedding_text_sha256 in varchar2,
    p_embedding_vector_json in clob,
    p_reembedding_run_id    in number default null
  ) return number;

  procedure validate_reembedding_run(
    p_reembedding_run_id in number
  );

  procedure activate_reembedding_run(
    p_reembedding_run_id in number
  );

  procedure activate_profile(
    p_embedding_profile_id in number
  );

  function reembedding_run_status_json(
    p_reembedding_run_id in number
  ) return clob;
end knowledge_embedding_api;
/

--rollback drop package orac_code.knowledge_embedding_api;
