--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines controlled table access for llm_input_media_types.

--changeset clive:create_package_spec_orac_api_llm_input_media_types_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_api.llm_input_media_types_tapi
authid definer
as
  procedure ins(
    p_row in out orac_api.llm_input_media_types_v%rowtype
  );

  procedure upd(
    p_row in out orac_api.llm_input_media_types_v%rowtype
  );

  procedure del(
    p_media_type in orac_api.llm_input_media_types_v.media_type%type,
    p_row_version in orac_api.llm_input_media_types_v.row_version%type
  );
end llm_input_media_types_tapi;
/
--rollback drop package orac_api.llm_input_media_types_tapi;

