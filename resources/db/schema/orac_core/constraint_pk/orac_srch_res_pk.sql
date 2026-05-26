-- __author__: clive
-- __date__: 2026-05-26
-- __description__: primary key for orac_search_results


alter table orac_core.orac_search_results
  add constraint orac_srch_res_pk
  primary key (search_result_id)
;

