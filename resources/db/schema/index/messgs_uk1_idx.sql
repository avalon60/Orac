-- uk index: orac.messages(conversation_id, turn_index)
create unique index orac.messgs_uk1_idx on orac.messages(conversation_id, turn_index);
