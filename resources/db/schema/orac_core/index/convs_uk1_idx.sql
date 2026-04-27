-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create unique index orac.convs_uk1_idx
  on orac.conversations
  (
    session_id asc
  )
;
