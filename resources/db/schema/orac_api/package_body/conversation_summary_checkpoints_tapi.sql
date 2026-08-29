--liquibase formatted sql
--changeset clive:create_package_body_orac_api_conversation_summary_checkpoints_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_api.conversation_summary_checkpoints_tapi
as
  procedure ins(p_row in out orac_api.conversation_summary_checkpoints_v%rowtype)
  is
  begin
    insert into orac_api.conversation_summary_checkpoints_v
    (
      conversation_id, first_turn_index, last_turn_index,
      materialisation_profile, source_digest, summary_text,
      summarisation_provider, summarisation_model, prompt_version,
      summary_embedding, embedding_model, embedding_provider,
      embedding_dimensions, distance_metric
    )
    values
    (
      p_row.conversation_id, p_row.first_turn_index, p_row.last_turn_index,
      p_row.materialisation_profile, p_row.source_digest, p_row.summary_text,
      p_row.summarisation_provider, p_row.summarisation_model, p_row.prompt_version,
      p_row.summary_embedding, p_row.embedding_model, p_row.embedding_provider,
      p_row.embedding_dimensions, p_row.distance_metric
    )
    returning checkpoint_id into p_row.checkpoint_id;
  end ins;
end conversation_summary_checkpoints_tapi;
/
--rollback drop package body orac_api.conversation_summary_checkpoints_tapi;
