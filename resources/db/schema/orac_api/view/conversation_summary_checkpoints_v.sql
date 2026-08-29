--liquibase formatted sql
--changeset clive:create_view_orac_api_conversation_summary_checkpoints_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.conversation_summary_checkpoints_v as
select checkpoint_id,
       conversation_id,
       first_turn_index,
       last_turn_index,
       materialisation_profile,
       source_digest,
       summary_text,
       summarisation_provider,
       summarisation_model,
       prompt_version,
       summary_embedding,
       embedding_model,
       embedding_provider,
       embedding_dimensions,
       distance_metric,
       created_on,
       created_by
  from orac_core.conversation_summary_checkpoints;
--rollback drop view orac_api.conversation_summary_checkpoints_v;
