--liquibase formatted sql
--changeset clive:create_view_orac_api_conversation_summary_sources_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.conversation_summary_sources_v as
select checkpoint_source_id,
       checkpoint_id,
       message_id,
       source_position,
       turn_index,
       message_row_version,
       source_content_sha256,
       created_on,
       created_by
  from orac_core.conversation_summary_sources;
--rollback drop view orac_api.conversation_summary_sources_v;
