-- __author__: clive
-- __date__: 2026-05-26
-- __description__: primary key index for orac_fetched_sources


create unique index orac_core.orac_fch_src_pk
  on orac_core.orac_fetched_sources
  (
    fetched_source_id asc
  )
;

