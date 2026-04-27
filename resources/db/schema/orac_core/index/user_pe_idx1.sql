-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac.user_pe_idx1
  on orac.user_prompt_elements
  (
    user_id asc,
    category_code asc
  )
;
