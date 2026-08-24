--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines controlled table access for llm_model_input_limits.

--changeset clive:create_package_spec_orac_api_llm_model_input_limits_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_api.llm_model_input_limits_tapi
authid definer
as
  procedure ins(
    p_row in out orac_api.llm_model_input_limits_v%rowtype
  );

  procedure upd(
    p_row in out orac_api.llm_model_input_limits_v%rowtype
  );

  procedure del(
    p_model_input_limit_id in orac_api.llm_model_input_limits_v.model_input_limit_id%type,
    p_row_version in orac_api.llm_model_input_limits_v.row_version%type
  );
end llm_model_input_limits_tapi;
/
--rollback drop package orac_api.llm_model_input_limits_tapi;

