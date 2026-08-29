--liquibase formatted sql
--changeset clive:create_package_body_orac_api_conversation_summary_sources_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_api.conversation_summary_sources_tapi
as
  procedure ins(p_row in out orac_api.conversation_summary_sources_v%rowtype)
  is
  begin
    insert into orac_api.conversation_summary_sources_v
    (
      checkpoint_id, message_id, source_position, turn_index,
      message_row_version, source_content_sha256
    )
    values
    (
      p_row.checkpoint_id, p_row.message_id, p_row.source_position,
      p_row.turn_index, p_row.message_row_version, p_row.source_content_sha256
    )
    returning checkpoint_source_id into p_row.checkpoint_source_id;
  end ins;
end conversation_summary_sources_tapi;
/
--rollback drop package body orac_api.conversation_summary_sources_tapi;
