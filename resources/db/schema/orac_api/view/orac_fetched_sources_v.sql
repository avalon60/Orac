--liquibase formatted sql

--changeset clive:create_view_orac_api_orac_fetched_sources_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-12
-- __description__: API projection of retrieval fetched source cache rows

create or replace force view orac_api.orac_fetched_sources_v as
select fetched_source_id
     , search_result_id
     , url
     , title
     , source_name
     , content_type
     , fetched_text
     , excerpt
     , byte_count
     , fetched_on
     , created_by
     , updated_on
     , updated_by
     , row_version
  from orac_core.orac_fetched_sources;

--rollback drop view orac_api.orac_fetched_sources_v;
