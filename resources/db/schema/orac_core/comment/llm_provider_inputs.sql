--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Documents llm_provider_inputs.

--changeset clive:comment_orac_core_llm_provider_inputs context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.llm_provider_inputs is
  'Reviewed provider/API transport declarations separated from concrete-model behaviour.';

comment on column orac_core.llm_provider_inputs.provider_input_id is
  'Provider input identifier.';

comment on column orac_core.llm_provider_inputs.provider_code is
  'Reviewed provider adapter declaring the transport.';

comment on column orac_core.llm_provider_inputs.representation_code is
  'Controlled representation accepted by the provider transport.';

comment on column orac_core.llm_provider_inputs.media_type is
  'Optional canonical MIME constraint; absence makes no exact MIME claim.';

comment on column orac_core.llm_provider_inputs.evidence_state_domain_code is
  'Fixed CAPABILITY_EVIDENCE_STATE reference domain.';

comment on column orac_core.llm_provider_inputs.evidence_state_ref_value_code is
  'Provider-level API_DECLARED or REJECTED transport evidence.';

comment on column orac_core.llm_provider_inputs.adapter_status_domain_code is
  'Fixed ADAPTER_SUPPORT_STATUS reference domain.';

comment on column orac_core.llm_provider_inputs.adapter_status_ref_value_code is
  'Whether the reviewed Orac adapter implements the transport.';

comment on column orac_core.llm_provider_inputs.source_uri is
  'Reviewed provider documentation source for the declaration.';

comment on column orac_core.llm_provider_inputs.checked_on is
  'Timestamp when the provider documentation was checked.';

comment on column orac_core.llm_provider_inputs.effective_from is
  'Timestamp from which the transport declaration is effective.';

comment on column orac_core.llm_provider_inputs.effective_to is
  'Exclusive timestamp after which the declaration is no longer current.';

comment on column orac_core.llm_provider_inputs.reviewed_by is
  'Reviewer responsible for the transport declaration.';

comment on column orac_core.llm_provider_inputs.provenance is
  'Safe review provenance without prompts, content, paths, or secrets.';

comment on column orac_core.llm_provider_inputs.rejection_reason is
  'Required safe reason when provider transport evidence is REJECTED.';

comment on column orac_core.llm_provider_inputs.native_properties is
  'Optional versioned transport metadata constrained to the P2-03 JSON allowlist.';

comment on column orac_core.llm_provider_inputs.created_by is
  'Principal that created the row.';

comment on column orac_core.llm_provider_inputs.created_on is
  'Timestamp when the row was created.';

comment on column orac_core.llm_provider_inputs.updated_by is
  'Principal that most recently updated the row.';

comment on column orac_core.llm_provider_inputs.updated_on is
  'Timestamp when the row was most recently updated.';

comment on column orac_core.llm_provider_inputs.row_version is
  'Optimistic-locking value incremented for each update.';
