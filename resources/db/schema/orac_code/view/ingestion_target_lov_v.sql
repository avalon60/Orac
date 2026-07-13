--liquibase formatted sql

--changeset clive:create_view_orac_code_ingestion_target_lov_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-11
-- __description__: shared ingestion target list of values for project routing

create or replace force view orac_code.ingestion_target_lov_v as
select 'project' target_scope_type
     , project_code target_scope_key
     , display_name || ' (' || project_code || ')' display_label
     , 10 sort_order
  from orac_api.project_registry_v
 where active_yn = 'Y';

--rollback drop view orac_code.ingestion_target_lov_v;
