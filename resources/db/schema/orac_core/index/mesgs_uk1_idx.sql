-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create unique index orac_core.mesgs_uk1_idx
  on orac_core.messages
  (
    conversation_id asc,
    turn_index asc
  )
;
