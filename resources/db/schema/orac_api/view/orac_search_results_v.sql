--liquibase formatted sql

--changeset clive:create_view_orac_api_orac_search_results_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-12
-- __description__: API projection of retrieval search result cache rows

create or replace force view orac_api.orac_search_results_v as
select search_result_id
     , search_query_id
     , result_rank
     , title
     , url
     , snippet
     , content
     , source_name
     , engine
     , created_on
     , created_by
     , updated_on
     , updated_by
     , row_version
  from orac_core.orac_search_results;

--rollback drop view orac_api.orac_search_results_v;
