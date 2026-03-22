-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create unique index orac.uq_conversations_session
  on orac.conversations
  (
    session_id asc
  )
;
