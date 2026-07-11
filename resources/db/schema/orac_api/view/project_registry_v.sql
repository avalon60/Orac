--liquibase formatted sql

--changeset clive:create_view_orac_api_project_registry_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-11
-- __description__: API projection of core project registry rows

create or replace force view orac_api.project_registry_v as
select project_id
     , project_code
     , display_name
     , description
     , active_yn
     , created_on
     , created_by
     , updated_on
     , updated_by
     , row_version
  from orac_core.project_registry;

--rollback drop view orac_api.project_registry_v;
