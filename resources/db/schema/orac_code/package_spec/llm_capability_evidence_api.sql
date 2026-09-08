--liquibase formatted sql
-- Author: clive
-- Date: 31-Aug-2026
-- Description: Defines the narrow runtime model-capability evidence lifecycle.

--changeset clive:create_package_spec_orac_code_llm_capability_evidence_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package orac_code.llm_capability_evidence_api
authid definer
as
  procedure reconcile_tool_metadata(
    p_llm_id          in number,
    p_provider_code   in varchar2,
    p_model_identity  in varchar2,
    p_model_revision  in varchar2,
    p_tools_declared  in varchar2
  );

  procedure record_probe_outcome(
    p_llm_id          in number,
    p_provider_code   in varchar2,
    p_model_identity  in varchar2,
    p_model_revision  in varchar2,
    p_capability_code in varchar2,
    p_outcome_code    in varchar2,
    p_probe_identity  in varchar2
  );
end llm_capability_evidence_api;
/
--rollback drop package orac_code.llm_capability_evidence_api;
