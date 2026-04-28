-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.llm_registry
  add constraint llm_reg_uk1
  unique (name)
;
