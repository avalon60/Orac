--liquibase formatted sql

--changeset clive:create_package_body_orac_api_project_registry_tapi context:core labels:core stripComments:false endDelimiter:/ runOnChange:true splitStatements:false
-- __author__: clive
-- __date__: 2026-07-11
-- __description__: table API body for project_registry

create or replace package body orac_api.project_registry_tapi
as
  procedure ins(
    p_row in out orac_api.project_registry_v%rowtype
  )
  is
  begin
    insert into orac_api.project_registry_v
      (
        project_code,
        display_name,
        description,
        active_yn
      )
    values
      (
        p_row.project_code,
        p_row.display_name,
        p_row.description,
        p_row.active_yn
      )
    returning project_id, row_version
         into p_row.project_id, p_row.row_version;
  end ins;

  procedure upd(
    p_project_id in     orac_api.project_registry_v.project_id%type,
    p_row        in out orac_api.project_registry_v%rowtype,
    p_row_version in    orac_api.project_registry_v.row_version%type
  )
  is
  begin
    update orac_api.project_registry_v
       set display_name = p_row.display_name
         , description  = p_row.description
         , active_yn    = p_row.active_yn
     where project_id = p_project_id
       and row_version = p_row_version
    returning row_version into p_row.row_version;

    if sql%rowcount = 0
    then
      raise no_data_found;
    end if;
  end upd;

  procedure del(
    p_project_id  in orac_api.project_registry_v.project_id%type,
    p_row_version in orac_api.project_registry_v.row_version%type
  )
  is
  begin
    delete from orac_api.project_registry_v
     where project_id = p_project_id
       and row_version = p_row_version;

    if sql%rowcount = 0
    then
      raise no_data_found;
    end if;
  end del;
end project_registry_tapi;
/

--rollback drop package body orac_api.project_registry_tapi;
