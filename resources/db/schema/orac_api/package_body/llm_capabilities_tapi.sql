--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Implements controlled table access for llm_capabilities.

--changeset clive:create_package_body_orac_api_llm_capabilities_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_api.llm_capabilities_tapi
as
  procedure assert_one_row(
    p_operation in varchar2
  )
  is
  begin
    if sql%rowcount <> 1
    then
      raise_application_error(
        -20644,
        p_operation || ' failed because the row is missing or stale.'
      );
    end if;
  end assert_one_row;

  procedure ins(
    p_row in out orac_api.llm_capabilities_v%rowtype
  )
  is
  begin
    insert into orac_api.llm_capabilities_v (
        capability_code
      , display_name
      , capability_class_domain_code
      , capability_class_ref_value_code
      , capability_lifecycle_domain_code
      , capability_lifecycle_ref_value_code
      , behaviour_summary
    ) values (
        p_row.capability_code
      , p_row.display_name
      , p_row.capability_class_domain_code
      , p_row.capability_class_ref_value_code
      , p_row.capability_lifecycle_domain_code
      , p_row.capability_lifecycle_ref_value_code
      , p_row.behaviour_summary
    )
    returning
                created_by
              , created_on
              , row_version
         into
                p_row.created_by
              , p_row.created_on
              , p_row.row_version;
  end ins;

  procedure upd(
    p_row in out orac_api.llm_capabilities_v%rowtype
  )
  is
  begin
    update orac_api.llm_capabilities_v
       set
         display_name = p_row.display_name
       , capability_class_domain_code = p_row.capability_class_domain_code
       , capability_class_ref_value_code = p_row.capability_class_ref_value_code
       , capability_lifecycle_domain_code = p_row.capability_lifecycle_domain_code
       , capability_lifecycle_ref_value_code = p_row.capability_lifecycle_ref_value_code
       , behaviour_summary = p_row.behaviour_summary
     where capability_code = p_row.capability_code
       and row_version = p_row.row_version;

    assert_one_row('Update');

    select row_version,
           updated_by,
           updated_on
      into p_row.row_version,
           p_row.updated_by,
           p_row.updated_on
      from orac_api.llm_capabilities_v
     where capability_code = p_row.capability_code;
  end upd;

  procedure del(
    p_capability_code in orac_api.llm_capabilities_v.capability_code%type,
    p_row_version in orac_api.llm_capabilities_v.row_version%type
  )
  is
  begin
    delete from orac_api.llm_capabilities_v
     where capability_code = p_capability_code
       and row_version = p_row_version;

    assert_one_row('Delete');
  end del;
end llm_capabilities_tapi;
/
--rollback drop package body orac_api.llm_capabilities_tapi;

