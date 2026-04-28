-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.messages
  add constraint mesgs_convs_fk1
  foreign key
  (
    conversation_id
  )
  references orac_core.conversations
  (
    conversation_id
  )
  on delete cascade
;
