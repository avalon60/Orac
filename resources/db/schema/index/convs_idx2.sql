-- idx: conversations by llm
create index orac.convs_idx2 on orac.conversations(llm_id);
