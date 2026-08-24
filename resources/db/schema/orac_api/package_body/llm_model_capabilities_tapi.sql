--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Implements controlled table access for llm_model_capabilities.

--changeset clive:create_package_body_orac_api_llm_model_capabilities_tapi context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_api.llm_model_capabilities_tapi
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
    p_row in out orac_api.llm_model_capabilities_v%rowtype
  )
  is
  begin
    insert into orac_api.llm_model_capabilities_v (
        llm_id
      , provider_code
      , model_identity
      , capability_code
      , evidence_state_domain_code
      , evidence_state_ref_value_code
      , model_revision
      , source_reference
      , checked_on
      , effective_from
      , effective_to
      , reviewed_by
      , provenance
      , fixture_identity
      , probe_identity
      , acceptance_criteria_ref
      , rejection_reason
      , native_properties
    ) values (
        p_row.llm_id
      , p_row.provider_code
      , p_row.model_identity
      , p_row.capability_code
      , p_row.evidence_state_domain_code
      , p_row.evidence_state_ref_value_code
      , p_row.model_revision
      , p_row.source_reference
      , p_row.checked_on
      , p_row.effective_from
      , p_row.effective_to
      , p_row.reviewed_by
      , p_row.provenance
      , p_row.fixture_identity
      , p_row.probe_identity
      , p_row.acceptance_criteria_ref
      , p_row.rejection_reason
      , p_row.native_properties
    )
    returning
                model_capability_id
              , created_by
              , created_on
              , row_version
         into
                p_row.model_capability_id
              , p_row.created_by
              , p_row.created_on
              , p_row.row_version;
  end ins;

  procedure upd(
    p_row in out orac_api.llm_model_capabilities_v%rowtype
  )
  is
  begin
    update orac_api.llm_model_capabilities_v
       set
         llm_id = p_row.llm_id
       , provider_code = p_row.provider_code
       , model_identity = p_row.model_identity
       , capability_code = p_row.capability_code
       , evidence_state_domain_code = p_row.evidence_state_domain_code
       , evidence_state_ref_value_code = p_row.evidence_state_ref_value_code
       , model_revision = p_row.model_revision
       , source_reference = p_row.source_reference
       , checked_on = p_row.checked_on
       , effective_from = p_row.effective_from
       , effective_to = p_row.effective_to
       , reviewed_by = p_row.reviewed_by
       , provenance = p_row.provenance
       , fixture_identity = p_row.fixture_identity
       , probe_identity = p_row.probe_identity
       , acceptance_criteria_ref = p_row.acceptance_criteria_ref
       , rejection_reason = p_row.rejection_reason
       , native_properties = p_row.native_properties
     where model_capability_id = p_row.model_capability_id
       and row_version = p_row.row_version;

    assert_one_row('Update');

    select row_version,
           updated_by,
           updated_on
      into p_row.row_version,
           p_row.updated_by,
           p_row.updated_on
      from orac_api.llm_model_capabilities_v
     where model_capability_id = p_row.model_capability_id;
  end upd;

  procedure del(
    p_model_capability_id in orac_api.llm_model_capabilities_v.model_capability_id%type,
    p_row_version in orac_api.llm_model_capabilities_v.row_version%type
  )
  is
  begin
    delete from orac_api.llm_model_capabilities_v
     where model_capability_id = p_model_capability_id
       and row_version = p_row_version;

    assert_one_row('Delete');
  end del;
end llm_model_capabilities_tapi;
/
--rollback drop package body orac_api.llm_model_capabilities_tapi;

