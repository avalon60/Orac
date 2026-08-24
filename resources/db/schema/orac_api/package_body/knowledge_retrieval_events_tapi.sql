--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Implements insert-only retrieval audit access.

--changeset clive:create_package_body_orac_api_knowledge_retrieval_events_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_api.knowledge_retrieval_events_tapi
as
  procedure ins(
    p_row in out orac_api.knowledge_retrieval_events_v%rowtype
  )
  is
  begin
    insert into orac_core.knowledge_retrieval_events (
      retrieval_id, event_type_code, event_on, username_snapshot,
      user_id, knowledge_scope_id, operation_code, target_type_code,
      target_id, status_code, reason_code, expected_byte_size,
      returned_byte_size, returned_sha256, member_count, chunk_count,
      duration_ms, detail_json
    ) values (
      p_row.retrieval_id, p_row.event_type_code,
      coalesce(p_row.event_on, systimestamp), p_row.username_snapshot,
      p_row.user_id, p_row.knowledge_scope_id, p_row.operation_code,
      p_row.target_type_code, p_row.target_id, p_row.status_code,
      p_row.reason_code, p_row.expected_byte_size, p_row.returned_byte_size,
      p_row.returned_sha256, p_row.member_count, p_row.chunk_count,
      p_row.duration_ms, p_row.detail_json
    )
    returning retrieval_event_id, event_on, created_by, created_on
         into p_row.retrieval_event_id, p_row.event_on,
              p_row.created_by, p_row.created_on;
  end ins;
end knowledge_retrieval_events_tapi;
/
--rollback drop package body orac_api.knowledge_retrieval_events_tapi;
