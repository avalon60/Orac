--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Documents llm_capabilities.

--changeset clive:comment_orac_core_llm_capabilities context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.llm_capabilities is
  'Provider-neutral P2-02 capability definitions without operational enablement.';

comment on column orac_core.llm_capabilities.capability_code is
  'Capability code.';

comment on column orac_core.llm_capabilities.display_name is
  'Human-readable provider-neutral capability name.';

comment on column orac_core.llm_capabilities.capability_class_domain_code is
  'Fixed CAPABILITY_CLASS reference domain.';

comment on column orac_core.llm_capabilities.capability_class_ref_value_code is
  'Provider-neutral P2-02 capability class.';

comment on column orac_core.llm_capabilities.capability_lifecycle_domain_code is
  'Fixed CAPABILITY_LIFECYCLE reference domain.';

comment on column orac_core.llm_capabilities.capability_lifecycle_ref_value_code is
  'Planning lifecycle without operational enablement semantics.';

comment on column orac_core.llm_capabilities.behaviour_summary is
  'Concise provider-neutral behavioural outcome.';

comment on column orac_core.llm_capabilities.created_by is
  'Principal that created the row.';

comment on column orac_core.llm_capabilities.created_on is
  'Timestamp when the row was created.';

comment on column orac_core.llm_capabilities.updated_by is
  'Principal that most recently updated the row.';

comment on column orac_core.llm_capabilities.updated_on is
  'Timestamp when the row was most recently updated.';

comment on column orac_core.llm_capabilities.row_version is
  'Optimistic-locking value incremented for each update.';
