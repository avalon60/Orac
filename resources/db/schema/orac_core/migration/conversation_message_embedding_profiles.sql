--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 29-Aug-2026
-- Description: Allows immutable conversation sources to retain multiple embedding profiles.

--changeset clive:expand_orac_core_mesg_emb_uk1_for_model_profiles context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:2 select count(*) from all_cons_columns where owner = 'ORAC_CORE' and constraint_name = 'MESG_EMB_UK1' and column_name in ('MESSAGE_ID', 'CHUNK_INDEX');
alter table orac_core.message_embeddings drop constraint mesg_emb_uk1;
drop index orac_core.mesg_emb_uk1_idx;
create unique index orac_core.mesg_emb_uk1_idx
  on orac_core.message_embeddings (
    message_id,
    chunk_index,
    embedding_model
  );
alter table orac_core.message_embeddings add constraint mesg_emb_uk1
  unique (
    message_id,
    chunk_index,
    embedding_model
  )
  using index orac_core.mesg_emb_uk1_idx;
--rollback alter table orac_core.message_embeddings drop constraint mesg_emb_uk1; drop index orac_core.mesg_emb_uk1_idx; create unique index orac_core.mesg_emb_uk1_idx on orac_core.message_embeddings (message_id, chunk_index); alter table orac_core.message_embeddings add constraint mesg_emb_uk1 unique (message_id, chunk_index) using index orac_core.mesg_emb_uk1_idx;
