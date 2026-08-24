--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines controlled table access for llm_input_representations.

--changeset clive:create_package_spec_orac_api_llm_input_representations_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_api.llm_input_representations_tapi
authid definer
as
  procedure ins(
    p_row in out orac_api.llm_input_representations_v%rowtype
  );

  procedure upd(
    p_row in out orac_api.llm_input_representations_v%rowtype
  );

  procedure del(
    p_representation_code in orac_api.llm_input_representations_v.representation_code%type,
    p_row_version in orac_api.llm_input_representations_v.row_version%type
  );
end llm_input_representations_tapi;
/
--rollback drop package orac_api.llm_input_representations_tapi;

