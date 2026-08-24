--liquibase formatted sql

--changeset clive:comment_orac_core_domain_ref_values context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.domain_ref_values is
  'Stores the selectable reference values belonging to Core-owned reference-data domains.';

comment on column orac_core.domain_ref_values.domain_code is
  'Reference-data domain that owns the value and forms part of its primary key.';

comment on column orac_core.domain_ref_values.ref_value_code is
  'Stable code stored or exchanged when the reference value is selected.';

comment on column orac_core.domain_ref_values.parent_domain_code is
  'Optional domain code of the reference value used to group or classify this value.';

comment on column orac_core.domain_ref_values.parent_ref_value_code is
  'Optional reference value code used with PARENT_DOMAIN_CODE to identify this value''s parent.';

comment on column orac_core.domain_ref_values.display_value is
  'Human-readable value shown in administration surfaces and LOVs.';

comment on column orac_core.domain_ref_values.description is
  'Optional explanation of the reference value meaning and intended use.';

comment on column orac_core.domain_ref_values.display_sequence is
  'Display ordering within the owning domain.';

comment on column orac_core.domain_ref_values.icon is
  'Optional icon identifier used by supporting user interfaces.';

comment on column orac_core.domain_ref_values.color is
  'Optional colour value used by supporting user interfaces.';

comment on column orac_core.domain_ref_values.active_yn is
  'Y when the value may be offered for new selections.';

comment on column orac_core.domain_ref_values.system_required_yn is
  'Y when the value is supplied by the hosting application and cannot be deleted.';

comment on column orac_core.domain_ref_values.created_by is
  'User or process that created the reference value.';

comment on column orac_core.domain_ref_values.created_on is
  'Timestamp when the reference value was created.';

comment on column orac_core.domain_ref_values.updated_by is
  'User or process that last updated the reference value.';

comment on column orac_core.domain_ref_values.updated_on is
  'Timestamp when the reference value was last updated.';

comment on column orac_core.domain_ref_values.row_version is
  'Optimistic-lock version incremented whenever the reference value is updated.';

--rollback comment on column orac_core.domain_ref_values.row_version is null;
--rollback comment on column orac_core.domain_ref_values.updated_on is null;
--rollback comment on column orac_core.domain_ref_values.updated_by is null;
--rollback comment on column orac_core.domain_ref_values.created_on is null;
--rollback comment on column orac_core.domain_ref_values.created_by is null;
--rollback comment on column orac_core.domain_ref_values.system_required_yn is null;
--rollback comment on column orac_core.domain_ref_values.active_yn is null;
--rollback comment on column orac_core.domain_ref_values.color is null;
--rollback comment on column orac_core.domain_ref_values.icon is null;
--rollback comment on column orac_core.domain_ref_values.display_sequence is null;
--rollback comment on column orac_core.domain_ref_values.description is null;
--rollback comment on column orac_core.domain_ref_values.display_value is null;
--rollback comment on column orac_core.domain_ref_values.parent_ref_value_code is null;
--rollback comment on column orac_core.domain_ref_values.parent_domain_code is null;
--rollback comment on column orac_core.domain_ref_values.ref_value_code is null;
--rollback comment on column orac_core.domain_ref_values.domain_code is null;
--rollback comment on table orac_core.domain_ref_values is null;
