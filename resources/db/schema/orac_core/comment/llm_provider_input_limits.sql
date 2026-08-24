--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Documents llm_provider_input_limits.

--changeset clive:comment_orac_core_llm_provider_input_limits context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.llm_provider_input_limits is
  'Dimension-, operator-, value-, and unit-qualified provider transport bounds.';

comment on column orac_core.llm_provider_input_limits.provider_input_limit_id is
  'Provider input limit identifier.';

comment on column orac_core.llm_provider_input_limits.provider_input_id is
  'Provider transport declaration to which this limit applies.';

comment on column orac_core.llm_provider_input_limits.limit_dimension_domain_code is
  'Fixed LIMIT_DIMENSION reference domain.';

comment on column orac_core.llm_provider_input_limits.limit_dimension_ref_value_code is
  'Measured provider transport limit dimension.';

comment on column orac_core.llm_provider_input_limits.bound_operator_domain_code is
  'Fixed BOUND_OPERATOR reference domain.';

comment on column orac_core.llm_provider_input_limits.bound_operator_ref_value_code is
  'Controlled comparison operator for the bound.';

comment on column orac_core.llm_provider_input_limits.limit_value is
  'Non-negative numeric bound value.';

comment on column orac_core.llm_provider_input_limits.limit_unit_domain_code is
  'Fixed LIMIT_UNIT reference domain.';

comment on column orac_core.llm_provider_input_limits.limit_unit_ref_value_code is
  'Controlled unit qualifying the numeric bound.';

comment on column orac_core.llm_provider_input_limits.effective_from is
  'Timestamp from which the bound is effective.';

comment on column orac_core.llm_provider_input_limits.effective_to is
  'Exclusive timestamp after which the bound is no longer current.';

comment on column orac_core.llm_provider_input_limits.provenance is
  'Safe source or review identity supporting the bound.';

comment on column orac_core.llm_provider_input_limits.created_by is
  'Principal that created the row.';

comment on column orac_core.llm_provider_input_limits.created_on is
  'Timestamp when the row was created.';

comment on column orac_core.llm_provider_input_limits.updated_by is
  'Principal that most recently updated the row.';

comment on column orac_core.llm_provider_input_limits.updated_on is
  'Timestamp when the row was most recently updated.';

comment on column orac_core.llm_provider_input_limits.row_version is
  'Optimistic-locking value incremented for each update.';
