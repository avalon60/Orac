-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.conversations
  add constraint conversations_ck1
  check (state in ('archived', 'closed', 'open'))
;
