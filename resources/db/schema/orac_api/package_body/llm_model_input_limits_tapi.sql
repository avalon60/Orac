--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Implements controlled table access for llm_model_input_limits.

--changeset clive:create_package_body_orac_api_llm_model_input_limits_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_api.llm_model_input_limits_tapi
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
    p_row in out orac_api.llm_model_input_limits_v%rowtype
  )
  is
  begin
    insert into orac_api.llm_model_input_limits_v (
        model_cap_input_id
      , limit_dimension_domain_code
      , limit_dimension_ref_value_code
      , bound_operator_domain_code
      , bound_operator_ref_value_code
      , limit_value
      , limit_unit_domain_code
      , limit_unit_ref_value_code
      , effective_from
      , effective_to
      , provenance
    ) values (
        p_row.model_cap_input_id
      , p_row.limit_dimension_domain_code
      , p_row.limit_dimension_ref_value_code
      , p_row.bound_operator_domain_code
      , p_row.bound_operator_ref_value_code
      , p_row.limit_value
      , p_row.limit_unit_domain_code
      , p_row.limit_unit_ref_value_code
      , p_row.effective_from
      , p_row.effective_to
      , p_row.provenance
    )
    returning
                model_input_limit_id
              , created_by
              , created_on
              , row_version
         into
                p_row.model_input_limit_id
              , p_row.created_by
              , p_row.created_on
              , p_row.row_version;
  end ins;

  procedure upd(
    p_row in out orac_api.llm_model_input_limits_v%rowtype
  )
  is
  begin
    update orac_api.llm_model_input_limits_v
       set
         model_cap_input_id = p_row.model_cap_input_id
       , limit_dimension_domain_code = p_row.limit_dimension_domain_code
       , limit_dimension_ref_value_code = p_row.limit_dimension_ref_value_code
       , bound_operator_domain_code = p_row.bound_operator_domain_code
       , bound_operator_ref_value_code = p_row.bound_operator_ref_value_code
       , limit_value = p_row.limit_value
       , limit_unit_domain_code = p_row.limit_unit_domain_code
       , limit_unit_ref_value_code = p_row.limit_unit_ref_value_code
       , effective_from = p_row.effective_from
       , effective_to = p_row.effective_to
       , provenance = p_row.provenance
     where model_input_limit_id = p_row.model_input_limit_id
       and row_version = p_row.row_version;

    assert_one_row('Update');

    select row_version,
           updated_by,
           updated_on
      into p_row.row_version,
           p_row.updated_by,
           p_row.updated_on
      from orac_api.llm_model_input_limits_v
     where model_input_limit_id = p_row.model_input_limit_id;
  end upd;

  procedure del(
    p_model_input_limit_id in orac_api.llm_model_input_limits_v.model_input_limit_id%type,
    p_row_version in orac_api.llm_model_input_limits_v.row_version%type
  )
  is
  begin
    delete from orac_api.llm_model_input_limits_v
     where model_input_limit_id = p_model_input_limit_id
       and row_version = p_row_version;

    assert_one_row('Delete');
  end del;
end llm_model_input_limits_tapi;
/
--rollback drop package body orac_api.llm_model_input_limits_tapi;

