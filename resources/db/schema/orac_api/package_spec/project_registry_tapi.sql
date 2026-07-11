--liquibase formatted sql

--changeset clive:create_package_spec_orac_api_project_registry_tapi context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-11
-- __description__: table API for project_registry

create or replace package orac_api.project_registry_tapi
authid definer
as
  procedure ins(
    p_row in out orac_api.project_registry_v%rowtype
  );

  procedure upd(
    p_project_id in     orac_api.project_registry_v.project_id%type,
    p_row        in out orac_api.project_registry_v%rowtype,
    p_row_version in    orac_api.project_registry_v.row_version%type
  );

  procedure del(
    p_project_id  in orac_api.project_registry_v.project_id%type,
    p_row_version in orac_api.project_registry_v.row_version%type
  );
end project_registry_tapi;
/

--rollback drop package orac_api.project_registry_tapi;
