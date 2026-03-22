-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.llm_registry
  add constraint llm_reg_cc1
  check (context_policy in ('app', 'external', 'hybrid', 'model'))
;
