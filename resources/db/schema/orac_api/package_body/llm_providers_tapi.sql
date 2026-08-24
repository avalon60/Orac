--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Implements controlled table access for llm_providers.

--changeset clive:create_package_body_orac_api_llm_providers_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_api.llm_providers_tapi
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
    p_row in out orac_api.llm_providers_v%rowtype
  )
  is
  begin
    insert into orac_api.llm_providers_v (
        provider_code
      , display_name
      , adapter_class
      , processing_locality_domain_code
      , processing_locality_ref_value_code
      , metadata_status_domain_code
      , metadata_status_ref_value_code
      , effective_from
      , effective_to
      , native_properties
    ) values (
        p_row.provider_code
      , p_row.display_name
      , p_row.adapter_class
      , p_row.processing_locality_domain_code
      , p_row.processing_locality_ref_value_code
      , p_row.metadata_status_domain_code
      , p_row.metadata_status_ref_value_code
      , p_row.effective_from
      , p_row.effective_to
      , p_row.native_properties
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
    p_row in out orac_api.llm_providers_v%rowtype
  )
  is
  begin
    update orac_api.llm_providers_v
       set
         display_name = p_row.display_name
       , adapter_class = p_row.adapter_class
       , processing_locality_domain_code = p_row.processing_locality_domain_code
       , processing_locality_ref_value_code = p_row.processing_locality_ref_value_code
       , metadata_status_domain_code = p_row.metadata_status_domain_code
       , metadata_status_ref_value_code = p_row.metadata_status_ref_value_code
       , effective_from = p_row.effective_from
       , effective_to = p_row.effective_to
       , native_properties = p_row.native_properties
     where provider_code = p_row.provider_code
       and row_version = p_row.row_version;

    assert_one_row('Update');

    select row_version,
           updated_by,
           updated_on
      into p_row.row_version,
           p_row.updated_by,
           p_row.updated_on
      from orac_api.llm_providers_v
     where provider_code = p_row.provider_code;
  end upd;

  procedure del(
    p_provider_code in orac_api.llm_providers_v.provider_code%type,
    p_row_version in orac_api.llm_providers_v.row_version%type
  )
  is
  begin
    delete from orac_api.llm_providers_v
     where provider_code = p_provider_code
       and row_version = p_row_version;

    assert_one_row('Delete');
  end del;
end llm_providers_tapi;
/
--rollback drop package body orac_api.llm_providers_tapi;

