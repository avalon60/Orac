-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac.ix_conversations_user_id
  on orac.conversations
  (
    user_id asc
  )
;
