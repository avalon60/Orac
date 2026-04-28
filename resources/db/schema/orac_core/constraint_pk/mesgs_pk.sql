-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.messages
  add constraint mesgs_pk
  primary key (message_id)
;
