--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Documents llm_model_capabilities.

--changeset clive:comment_orac_core_llm_model_capabilities context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.llm_model_capabilities is
  'Dated reviewed behavioural evidence for one exact registered model and capability.';

comment on column orac_core.llm_model_capabilities.model_capability_id is
  'Model capability identifier.';

comment on column orac_core.llm_model_capabilities.llm_id is
  'Registered model configuration to which the evidence applies.';

comment on column orac_core.llm_model_capabilities.provider_code is
  'Exact reviewed provider identity copied from the registry relationship.';

comment on column orac_core.llm_model_capabilities.model_identity is
  'Exact provider model identifier copied from the registry relationship.';

comment on column orac_core.llm_model_capabilities.capability_code is
  'Provider-neutral behaviour assessed by this evidence.';

comment on column orac_core.llm_model_capabilities.evidence_state_domain_code is
  'Fixed CAPABILITY_EVIDENCE_STATE reference domain.';

comment on column orac_core.llm_model_capabilities.evidence_state_ref_value_code is
  'Evidence maturity. MODEL_METADATA_VERIFIED verifies only the exact provider declaration; demonstrated model behaviour requires BOUNDED_PROBE_VERIFIED.';

comment on column orac_core.llm_model_capabilities.model_revision is
  'Immutable model revision or digest reviewed for the evidence.';

comment on column orac_core.llm_model_capabilities.source_reference is
  'Source URI or bounded probe identity supporting the evidence.';

comment on column orac_core.llm_model_capabilities.checked_on is
  'Timestamp when the evidence was reviewed.';

comment on column orac_core.llm_model_capabilities.effective_from is
  'Timestamp from which the evidence is effective.';

comment on column orac_core.llm_model_capabilities.effective_to is
  'Exclusive timestamp after which the evidence is not current.';

comment on column orac_core.llm_model_capabilities.reviewed_by is
  'Reviewer responsible for the evidence decision.';

comment on column orac_core.llm_model_capabilities.provenance is
  'Safe evidence provenance without prompts, content, paths, or secrets.';

comment on column orac_core.llm_model_capabilities.fixture_identity is
  'Approved safe fixture identity required for bounded-probe evidence.';

comment on column orac_core.llm_model_capabilities.probe_identity is
  'Bounded probe execution identity required for bounded-probe evidence.';

comment on column orac_core.llm_model_capabilities.acceptance_criteria_ref is
  'Approved acceptance-criteria reference required for bounded-probe evidence.';

comment on column orac_core.llm_model_capabilities.rejection_reason is
  'Required safe reason for REJECTED evidence and forbidden for positive evidence.';

comment on column orac_core.llm_model_capabilities.native_properties is
  'Optional versioned evidence metadata constrained to the P2-03 JSON allowlist.';

comment on column orac_core.llm_model_capabilities.created_by is
  'Principal that created the row.';

comment on column orac_core.llm_model_capabilities.created_on is
  'Timestamp when the row was created.';

comment on column orac_core.llm_model_capabilities.updated_by is
  'Principal that most recently updated the row.';

comment on column orac_core.llm_model_capabilities.updated_on is
  'Timestamp when the row was most recently updated.';

comment on column orac_core.llm_model_capabilities.row_version is
  'Optimistic-locking value incremented for each update.';
