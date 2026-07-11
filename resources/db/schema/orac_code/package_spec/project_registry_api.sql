--liquibase formatted sql

--changeset clive:create_package_spec_orac_code_project_registry_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
-- __author__: clive
-- __date__: 2026-07-11
-- __description__: controlled project registry maintenance API

create or replace package orac_code.project_registry_api as
  procedure create_project(
    p_project_code in orac_api.project_registry_v.project_code%type,
    p_display_name in orac_api.project_registry_v.display_name%type,
    p_description  in orac_api.project_registry_v.description%type default null,
    p_active_yn    in orac_api.project_registry_v.active_yn%type default 'Y'
  );

  procedure update_project(
    p_project_id   in orac_api.project_registry_v.project_id%type,
    p_project_code in orac_api.project_registry_v.project_code%type,
    p_display_name in orac_api.project_registry_v.display_name%type,
    p_description  in orac_api.project_registry_v.description%type default null,
    p_active_yn    in orac_api.project_registry_v.active_yn%type default 'Y',
    p_row_checksum in varchar2
  );

  procedure deactivate_project(
    p_project_id   in orac_api.project_registry_v.project_id%type,
    p_row_checksum in varchar2
  );

  procedure upsert_project(
    p_project_code in orac_api.project_registry_v.project_code%type,
    p_display_name in orac_api.project_registry_v.display_name%type,
    p_description  in orac_api.project_registry_v.description%type default null,
    p_active_yn    in orac_api.project_registry_v.active_yn%type default 'Y'
  );
end project_registry_api;
/

--rollback drop package orac_code.project_registry_api;
