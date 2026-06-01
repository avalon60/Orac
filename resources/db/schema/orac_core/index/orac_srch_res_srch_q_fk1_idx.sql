-- __author__: clive
-- __date__: 2026-05-26
-- __description__: foreign key index for orac_search_results to orac_search_queries


create index orac_core.orac_srch_res_srch_q_fk1_idx
  on orac_core.orac_search_results
  (
    search_query_id asc
  )
;

