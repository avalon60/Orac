-- __author__: clive
-- __date__: 2026-05-26
-- __description__: search query foreign key for orac_search_results


alter table orac_core.orac_search_results
  add constraint orac_srch_res_orac_srch_q_fk1
  foreign key
  (
    search_query_id
  )
  references orac_core.orac_search_queries
  (
    search_query_id
  )
;

