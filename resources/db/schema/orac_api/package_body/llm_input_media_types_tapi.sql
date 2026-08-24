--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Implements controlled table access for llm_input_media_types.

--changeset clive:create_package_body_orac_api_llm_input_media_types_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_api.llm_input_media_types_tapi
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
    p_row in out orac_api.llm_input_media_types_v%rowtype
  )
  is
  begin
    insert into orac_api.llm_input_media_types_v (
        media_type
      , display_name
      , mime_match_kind_domain_code
      , mime_match_kind_ref_value_code
      , description
    ) values (
        p_row.media_type
      , p_row.display_name
      , p_row.mime_match_kind_domain_code
      , p_row.mime_match_kind_ref_value_code
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
    p_row in out orac_api.llm_input_media_types_v%rowtype
  )
  is
  begin
    update orac_api.llm_input_media_types_v
       set
         display_name = p_row.display_name
       , mime_match_kind_domain_code = p_row.mime_match_kind_domain_code
       , mime_match_kind_ref_value_code = p_row.mime_match_kind_ref_value_code
       , description = p_row.description
     where media_type = p_row.media_type
       and row_version = p_row.row_version;

    assert_one_row('Update');

    select row_version,
           updated_by,
           updated_on
      into p_row.row_version,
           p_row.updated_by,
           p_row.updated_on
      from orac_api.llm_input_media_types_v
     where media_type = p_row.media_type;
  end upd;

  procedure del(
    p_media_type in orac_api.llm_input_media_types_v.media_type%type,
    p_row_version in orac_api.llm_input_media_types_v.row_version%type
  )
  is
  begin
    delete from orac_api.llm_input_media_types_v
     where media_type = p_media_type
       and row_version = p_row_version;

    assert_one_row('Delete');
  end del;
end llm_input_media_types_tapi;
/
--rollback drop package body orac_api.llm_input_media_types_tapi;

