--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines controlled table access for llm_capabilities.

--changeset clive:create_package_spec_orac_api_llm_capabilities_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_api.llm_capabilities_tapi
authid definer
as
  procedure ins(
    p_row in out orac_api.llm_capabilities_v%rowtype
  );

  procedure upd(
    p_row in out orac_api.llm_capabilities_v%rowtype
  );

  procedure del(
    p_capability_code in orac_api.llm_capabilities_v.capability_code%type,
    p_row_version in orac_api.llm_capabilities_v.row_version%type
  );
end llm_capabilities_tapi;
/
--rollback drop package orac_api.llm_capabilities_tapi;

