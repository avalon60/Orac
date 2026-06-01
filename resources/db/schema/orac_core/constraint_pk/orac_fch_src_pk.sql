-- __author__: clive
-- __date__: 2026-05-26
-- __description__: primary key for orac_fetched_sources


alter table orac_core.orac_fetched_sources
  add constraint orac_fch_src_pk
  primary key (fetched_source_id)
;

