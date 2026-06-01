-- __author__: clive
-- __date__: 2026-05-26
-- __description__: search result foreign key for orac_fetched_sources


alter table orac_core.orac_fetched_sources
  add constraint orac_fch_src_srch_res_fk1
  foreign key
  (
    search_result_id
  )
  references orac_core.orac_search_results
  (
    search_result_id
  )
;

