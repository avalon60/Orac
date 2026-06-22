--liquibase formatted sql

--changeset clive:comment_orac_core_comment_message_embeddings context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.message_embeddings is
  'Embeddings for message-level chunks.'
;

comment on column orac_core.message_embeddings.message_id is
  'FK to orac_core.messages.message_id.'
;

comment on column orac_core.message_embeddings.chunk_index is
  '1-based ordinal of chunk within the message.'
;
