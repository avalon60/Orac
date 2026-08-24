--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 13-Aug-2026
-- Description: Exposes controlled retrieval audit rows to the business layer.

--changeset clive:create_view_orac_api_knowledge_retrieval_events_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.knowledge_retrieval_events_v as
select retrieval_event_id,
       retrieval_id,
       event_type_code,
       event_on,
       username_snapshot,
       user_id,
       knowledge_scope_id,
       operation_code,
       target_type_code,
       target_id,
       status_code,
       reason_code,
       expected_byte_size,
       returned_byte_size,
       returned_sha256,
       member_count,
       chunk_count,
       duration_ms,
       detail_json,
       created_by,
       created_on
  from orac_core.knowledge_retrieval_events;
--rollback drop view orac_api.knowledge_retrieval_events_v;
