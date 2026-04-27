comment on table orac.message_embeddings is
  'Embeddings for message-level chunks.'
;

comment on column orac.message_embeddings.message_id is
  'FK to orac.messages.message_id.'
;

comment on column orac.message_embeddings.chunk_index is
  '1-based ordinal of chunk within the message.'
;
