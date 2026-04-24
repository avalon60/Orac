-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac.user_prompt_elements
  add constraint user_prompt_elements_cc1
  check (is_enabled in ('N', 'Y'))
;
