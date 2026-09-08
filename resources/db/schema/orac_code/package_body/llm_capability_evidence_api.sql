--liquibase formatted sql
-- Author: clive
-- Date: 31-Aug-2026
-- Description: Implements exact-revision capability evidence reconciliation.

--changeset clive:create_package_body_orac_code_llm_capability_evidence_api context:core labels:core stripComments:false splitStatements:false endDelimiter:/ runOnChange:true
create or replace package body orac_code.llm_capability_evidence_api
as
  gc_structured constant varchar2(100) := 'structured_tool_calling';
  gc_streamed   constant varchar2(100) := 'streamed_structured_tool_calling';

  procedure assert_identity(
    p_llm_id         in number,
    p_provider_code  in varchar2,
    p_model_identity in varchar2,
    p_model_revision in varchar2
  )
  is
    l_count pls_integer;
  begin
    if p_model_revision is null or length(trim(p_model_revision)) < 8
    then
      raise_application_error(-20720, 'Exact model revision is required.');
    end if;

    select count(*)
      into l_count
      from orac_api.llm_registry_v
     where llm_id = p_llm_id
       and provider = lower(trim(p_provider_code))
       and model = trim(p_model_identity)
       and upper(is_enabled) = 'Y';

    if l_count <> 1
    then
      raise_application_error(-20721, 'Registered model identity is unavailable.');
    end if;
  end assert_identity;

  procedure close_current(
    p_llm_id          in number,
    p_capability_code in varchar2,
    p_except_revision in varchar2 default null
  )
  is
    l_row       orac_api.llm_model_capabilities_v%rowtype;
    l_closed_on timestamp with local time zone;
  begin
    for rec in (
      select model_capability_id,
             effective_from
        from orac_api.llm_model_capabilities_v
       where llm_id = p_llm_id
         and capability_code = p_capability_code
         and effective_to is null
         and (p_except_revision is null or model_revision <> p_except_revision)
    )
    loop
      select *
        into l_row
        from orac_api.llm_model_capabilities_v
       where model_capability_id = rec.model_capability_id;

      l_closed_on := systimestamp;
      if l_closed_on <= rec.effective_from
      then
        l_closed_on := rec.effective_from + numtodsinterval(0.001, 'SECOND');
      end if;
      l_row.effective_to := l_closed_on;
      orac_api.llm_model_capabilities_tapi.upd(l_row);
    end loop;
  end close_current;

  procedure insert_evidence(
    p_llm_id          in number,
    p_provider_code   in varchar2,
    p_model_identity  in varchar2,
    p_model_revision  in varchar2,
    p_capability_code in varchar2,
    p_evidence_state  in varchar2,
    p_probe_identity  in varchar2 default null
  )
  is
    l_row orac_api.llm_model_capabilities_v%rowtype;
  begin
    l_row.llm_id := p_llm_id;
    l_row.provider_code := lower(trim(p_provider_code));
    l_row.model_identity := trim(p_model_identity);
    l_row.capability_code := p_capability_code;
    l_row.evidence_state_domain_code := 'CAPABILITY_EVIDENCE_STATE';
    l_row.evidence_state_ref_value_code := p_evidence_state;
    l_row.model_revision := trim(p_model_revision);
    l_row.checked_on := systimestamp;
    l_row.effective_from := systimestamp;
    l_row.reviewed_by := 'ORAC_RUNTIME';

    if p_evidence_state = 'MODEL_METADATA_VERIFIED'
    then
      l_row.source_reference := 'provider_metadata:' || lower(trim(p_provider_code));
      l_row.provenance := 'startup_capability_reconciliation:v1';
    else
      l_row.source_reference := 'bounded_probe:' || trim(p_probe_identity);
      l_row.provenance := 'governed_tool_probe:v1';
      l_row.fixture_identity := 'orac-governed-tool-v1';
      l_row.probe_identity := trim(p_probe_identity);
      l_row.acceptance_criteria_ref := 'governed-tool-probe-v1';
      if p_evidence_state = 'REJECTED'
      then
        l_row.rejection_reason := 'PROBE_MODEL_REJECTED';
      end if;
    end if;

    orac_api.llm_model_capabilities_tapi.ins(l_row);
  end insert_evidence;

  procedure reconcile_tool_metadata(
    p_llm_id          in number,
    p_provider_code   in varchar2,
    p_model_identity  in varchar2,
    p_model_revision  in varchar2,
    p_tools_declared  in varchar2
  )
  is
    l_current_count pls_integer;
  begin
    assert_identity(
      p_llm_id,
      p_provider_code,
      p_model_identity,
      p_model_revision
    );
    if upper(trim(p_tools_declared)) not in ('Y', 'N')
    then
      raise_application_error(-20722, 'Tool declaration must be Y or N.');
    end if;

    close_current(p_llm_id, gc_structured, p_model_revision);
    close_current(p_llm_id, gc_streamed, p_model_revision);

    if upper(trim(p_tools_declared)) = 'N'
    then
      close_current(p_llm_id, gc_structured);
      close_current(p_llm_id, gc_streamed);
      return;
    end if;

    select count(*)
      into l_current_count
      from orac_api.llm_model_capabilities_v
     where llm_id = p_llm_id
       and capability_code = gc_structured
       and model_revision = trim(p_model_revision)
       and effective_to is null;

    if l_current_count = 0
    then
      insert_evidence(
        p_llm_id,
        p_provider_code,
        p_model_identity,
        p_model_revision,
        gc_structured,
        'MODEL_METADATA_VERIFIED'
      );
    end if;
  end reconcile_tool_metadata;

  procedure record_probe_outcome(
    p_llm_id          in number,
    p_provider_code   in varchar2,
    p_model_identity  in varchar2,
    p_model_revision  in varchar2,
    p_capability_code in varchar2,
    p_outcome_code    in varchar2,
    p_probe_identity  in varchar2
  )
  is
    l_desired_state    varchar2(100);
    l_current_state    varchar2(100);
    l_structured_count pls_integer;
  begin
    assert_identity(
      p_llm_id,
      p_provider_code,
      p_model_identity,
      p_model_revision
    );
    if p_capability_code not in (gc_structured, gc_streamed)
    then
      raise_application_error(-20723, 'Unsupported tool capability code.');
    end if;
    if upper(trim(p_outcome_code)) = 'PASS'
    then
      l_desired_state := 'BOUNDED_PROBE_VERIFIED';
    elsif upper(trim(p_outcome_code)) = 'MODEL_REJECTED'
    then
      l_desired_state := 'REJECTED';
    else
      raise_application_error(-20724, 'Unsupported probe outcome.');
    end if;
    if p_probe_identity is null
    then
      raise_application_error(-20725, 'Probe identity is required.');
    end if;

    if p_capability_code = gc_streamed
    then
      select count(*)
        into l_structured_count
        from orac_api.llm_model_capabilities_v
       where llm_id = p_llm_id
         and capability_code = gc_structured
         and model_revision = trim(p_model_revision)
         and evidence_state_ref_value_code = 'BOUNDED_PROBE_VERIFIED'
         and effective_to is null;
      if l_structured_count <> 1
      then
        raise_application_error(
          -20726,
          'Streamed evidence requires demonstrated structured behaviour.'
        );
      end if;
    end if;

    begin
      select evidence_state_ref_value_code
        into l_current_state
        from orac_api.llm_model_capabilities_v
       where llm_id = p_llm_id
         and capability_code = p_capability_code
         and model_revision = trim(p_model_revision)
         and effective_to is null;
    exception
      when no_data_found then
        l_current_state := null;
    end;

    if l_current_state = l_desired_state
    then
      return;
    end if;

    close_current(p_llm_id, p_capability_code);
    insert_evidence(
      p_llm_id,
      p_provider_code,
      p_model_identity,
      p_model_revision,
      p_capability_code,
      l_desired_state,
      p_probe_identity
    );
  end record_probe_outcome;
end llm_capability_evidence_api;
/
--rollback drop package body orac_code.llm_capability_evidence_api;
