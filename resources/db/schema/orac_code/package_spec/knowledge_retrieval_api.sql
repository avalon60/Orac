--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Defines the authorised knowledge retrieval boundary for Core runtime.

--changeset clive:create_package_spec_orac_code_knowledge_retrieval_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_code.knowledge_retrieval_api
authid definer
as
  procedure resolve_request(
    p_retrieval_id    in  varchar2,
    p_username        in  varchar2,
    p_scope_type      in  varchar2,
    p_scope_key       in  varchar2,
    p_request_json    in  clob,
    p_resolution_json out clob,
    p_content_rows    out sys_refcursor
  );

  procedure open_search_candidates(
    p_retrieval_id               in  varchar2,
    p_username                   in  varchar2,
    p_scope_type                 in  varchar2,
    p_scope_key                  in  varchar2,
    p_embedding_model_identifier in  varchar2,
    p_embedding_dimensions       in  number,
    p_candidate_limit            in  number,
    p_resolution_json            out clob,
    p_content_rows               out sys_refcursor
  );

  procedure record_policy_decision(
    p_policy_request_id       in varchar2,
    p_username                in varchar2,
    p_scope_type              in varchar2,
    p_scope_key               in varchar2,
    p_target_type             in varchar2,
    p_target_id               in number,
    p_decision_code           in varchar2,
    p_reason_code             in varchar2,
    p_purpose_code            in varchar2,
    p_requested_level_code    in varchar2,
    p_effective_level_code    in varchar2,
    p_policy_version          in varchar2,
    p_estimator_code          in varchar2,
    p_estimated_byte_size     in number default null,
    p_estimated_token_count   in number default null,
    p_usable_context_tokens   in number default null,
    p_member_count            in number default null,
    p_chunk_count             in number default null,
    p_complete_yn             in varchar2 default 'N',
    p_selected_yn             in varchar2 default 'N',
    p_downgraded_yn           in varchar2 default 'N',
    p_truncated_yn            in varchar2 default 'N'
  );

  procedure record_model_submission_decision(
    p_submission_id             in varchar2,
    p_policy_request_id         in varchar2,
    p_username                  in varchar2,
    p_scope_type                in varchar2,
    p_scope_key                 in varchar2,
    p_target_type               in varchar2,
    p_target_id                 in number,
    p_llm_id                    in number,
    p_registry_row_version      in number,
    p_provider_capability_code  in varchar2,
    p_context_policy_code       in varchar2,
    p_envelope_version          in number,
    p_effective_level_code      in varchar2,
    p_part_count                in number,
    p_member_count              in number default null,
    p_chunk_count               in number default null,
    p_verified_source_bytes     in number,
    p_envelope_bytes            in number,
    p_evidence_tokens           in number,
    p_occupied_tokens           in number,
    p_final_input_tokens        in number,
    p_reserved_output_tokens    in number,
    p_safety_tokens             in number,
    p_complete_yn               in varchar2 default 'N',
    p_selected_yn               in varchar2 default 'N',
    p_downgraded_yn             in varchar2 default 'N',
    p_non_truncated_yn          in varchar2 default 'Y',
    p_retry_count               in number default 0,
    p_reason_code               in varchar2 default 'MAT_SUB_APPROVED'
  );

  procedure record_outcome(
    p_retrieval_id       in varchar2,
    p_outcome_code       in varchar2,
    p_reason_code        in varchar2,
    p_returned_byte_size in number default null,
    p_returned_sha256    in varchar2 default null,
    p_member_count       in number default null,
    p_chunk_count        in number default null,
    p_duration_ms        in number default null
  );
end knowledge_retrieval_api;
/
--rollback drop package orac_code.knowledge_retrieval_api;
