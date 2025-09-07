-- uk index: orac.message_embeddings(message_id, chunk_index)
create unique index orac.megemb_uk1_idx on orac.message_embeddings(message_id, chunk_index);
