--liquibase formatted sql
-- Author: clive
-- Date: 28-Aug-2026
-- Description: Defines governed conversational-memory materialisation and retrieval.

--changeset clive:create_package_spec_orac_code_conversation_memory_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_code.conversation_memory_api
authid definer
as
  function reconcile_eligible_ranges(
    p_checkpoint_exchange_count in number,
    p_materialisation_profile   in varchar2,
    p_prompt_version            in varchar2,
    p_max_attempts              in number
  ) return number;

  function next_request_id return number;

  procedure open_request_sources(
    p_memory_request_id in number,
    p_sources              out sys_refcursor
  );

  procedure ensure_message_embedding(
    p_memory_request_id     in number,
    p_message_id            in number,
    p_source_row_version    in number,
    p_source_content_sha256 in varchar2,
    p_source_text           in clob,
    p_embedding_json        in clob,
    p_embedding_model       in varchar2,
    p_embedding_provider    in varchar2,
    p_token_count           in number
  );

  procedure complete_request(
    p_memory_request_id      in number,
    p_source_digest          in varchar2,
    p_summary_text           in clob,
    p_summarisation_provider in varchar2,
    p_summarisation_model    in varchar2,
    p_summary_embedding_json in clob,
    p_embedding_model        in varchar2,
    p_embedding_provider     in varchar2,
    p_embedding_dimensions   in number,
    p_source_lineage_json    in clob,
    p_checkpoint_id             out number
  );

  procedure record_failure(
    p_memory_request_id in number,
    p_error_code        in varchar2,
    p_error_message     in varchar2,
    p_retryable         in char
  );

  procedure open_summary_candidates(
    p_principal_username  in varchar2,
    p_embedding_model     in varchar2,
    p_embedding_dimensions in number,
    p_candidate_limit     in number,
    p_candidates             out sys_refcursor
  );

  procedure open_source_candidates(
    p_principal_username   in varchar2,
    p_checkpoint_ids_json in clob,
    p_embedding_model      in varchar2,
    p_embedding_dimensions in number,
    p_candidate_limit      in number,
    p_candidates              out sys_refcursor
  );
end conversation_memory_api;
/
--rollback drop package orac_code.conversation_memory_api;
