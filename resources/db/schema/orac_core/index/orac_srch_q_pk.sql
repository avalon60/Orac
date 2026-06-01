-- __author__: clive
-- __date__: 2026-05-26
-- __description__: primary key index for orac_search_queries


create unique index orac_core.orac_srch_q_pk
  on orac_core.orac_search_queries
  (
    search_query_id asc
  )
;

