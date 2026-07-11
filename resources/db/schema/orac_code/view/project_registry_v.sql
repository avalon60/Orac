--liquibase formatted sql

--changeset clive:create_view_orac_code_project_registry_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-07-11
-- __description__: supported project registry view for runtime and APEX surfaces

create or replace force view orac_code.project_registry_v as
select project_id
     , project_code
     , display_name
     , description
     , active_yn
     , standard_hash(
         project_id
         || ':' || project_code
         || ':' || display_name
         || ':' || nvl(description, chr(0))
         || ':' || active_yn
         || ':' || row_version,
         'SHA256'
       ) row_checksum
  from orac_api.project_registry_v;

--rollback drop view orac_code.project_registry_v;
