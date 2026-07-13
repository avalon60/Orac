--liquibase formatted sql

--changeset clive:create_view_orac_api_orac_search_queries_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-12
-- __description__: API projection of retrieval search query cache rows

create or replace force view orac_api.orac_search_queries_v as
select search_query_id
     , query_text
     , trigger_phrase
     , provider_name
     , max_results
     , created_on
     , created_by
     , updated_on
     , updated_by
     , row_version
  from orac_core.orac_search_queries;

--rollback drop view orac_api.orac_search_queries_v;
