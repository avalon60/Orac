-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac.mesgs_llm_reg_fk1_idx
  on orac.messages
  (
    llm_id asc
  )
;
