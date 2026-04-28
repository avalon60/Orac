-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create unique index orac_core.user_pe_pk_idx
  on orac_core.user_prompt_elements
  (
    element_id asc
  )
;
