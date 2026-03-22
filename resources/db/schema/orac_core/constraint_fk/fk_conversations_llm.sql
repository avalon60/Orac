-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.conversations
  add constraint fk_conversations_llm
  foreign key
  (
    llm_id
  )
  references orac.llm_registry
  (
    llm_id
  )
;
