-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac_core.mesgs_llm_reg_fk1_idx
  on orac_core.messages
  (
    llm_id asc
  )
;
