-- __author__: clive
-- __date__: 2026-05-26
-- __description__: foreign key index for orac_fetched_sources to orac_search_results


create index orac_core.orac_fch_src_srch_res_fk1_idx
  on orac_core.orac_fetched_sources
  (
    search_result_id asc
  )
;

