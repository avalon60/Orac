--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Implements controlled table access for llm_input_representations.

--changeset clive:create_package_body_orac_api_llm_input_representations_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_api.llm_input_representations_tapi
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
    p_row in out orac_api.llm_input_representations_v%rowtype
  )
  is
  begin
    insert into orac_api.llm_input_representations_v (
        representation_code
      , display_name
      , description
    ) values (
        p_row.representation_code
      , p_row.display_name
      , p_row.description
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
    p_row in out orac_api.llm_input_representations_v%rowtype
  )
  is
  begin
    update orac_api.llm_input_representations_v
       set
         display_name = p_row.display_name
       , description = p_row.description
     where representation_code = p_row.representation_code
       and row_version = p_row.row_version;

    assert_one_row('Update');

    select row_version,
           updated_by,
           updated_on
      into p_row.row_version,
           p_row.updated_by,
           p_row.updated_on
      from orac_api.llm_input_representations_v
     where representation_code = p_row.representation_code;
  end upd;

  procedure del(
    p_representation_code in orac_api.llm_input_representations_v.representation_code%type,
    p_row_version in orac_api.llm_input_representations_v.row_version%type
  )
  is
  begin
    delete from orac_api.llm_input_representations_v
     where representation_code = p_representation_code
       and row_version = p_row_version;

    assert_one_row('Delete');
  end del;
end llm_input_representations_tapi;
/
--rollback drop package body orac_api.llm_input_representations_tapi;

