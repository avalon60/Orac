-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create unique index orac_core.user_syns_pk
  on orac_core.user_synonyms
  (
    alias_type asc,
    alias_value asc
  )
;
