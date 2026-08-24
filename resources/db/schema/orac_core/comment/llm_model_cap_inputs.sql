--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Documents llm_model_cap_inputs.

--changeset clive:comment_orac_core_llm_model_cap_inputs context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.llm_model_cap_inputs is
  'Representations and optional MIME constraints accepted by positive model evidence.';

comment on column orac_core.llm_model_cap_inputs.model_cap_input_id is
  'Model capability input identifier.';

comment on column orac_core.llm_model_cap_inputs.model_capability_id is
  'Positive concrete-model evidence owning this input association.';

comment on column orac_core.llm_model_cap_inputs.representation_code is
  'Controlled representation accepted by the evidenced behaviour.';

comment on column orac_core.llm_model_cap_inputs.media_type is
  'Optional canonical MIME constraint for this representation.';

comment on column orac_core.llm_model_cap_inputs.effective_from is
  'Timestamp from which the input association is effective.';

comment on column orac_core.llm_model_cap_inputs.effective_to is
  'Exclusive timestamp after which the association is not current.';

comment on column orac_core.llm_model_cap_inputs.provenance is
  'Safe review provenance supporting the input association.';

comment on column orac_core.llm_model_cap_inputs.created_by is
  'Principal that created the row.';

comment on column orac_core.llm_model_cap_inputs.created_on is
  'Timestamp when the row was created.';

comment on column orac_core.llm_model_cap_inputs.updated_by is
  'Principal that most recently updated the row.';

comment on column orac_core.llm_model_cap_inputs.updated_on is
  'Timestamp when the row was most recently updated.';

comment on column orac_core.llm_model_cap_inputs.row_version is
  'Optimistic-locking value incremented for each update.';
