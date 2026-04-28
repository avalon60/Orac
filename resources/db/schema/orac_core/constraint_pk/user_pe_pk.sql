-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.user_prompt_elements
  add constraint user_pe_pk
  primary key (element_id)
;
