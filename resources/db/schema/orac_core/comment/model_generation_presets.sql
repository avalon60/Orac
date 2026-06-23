--liquibase formatted sql

--changeset clive:comment_orac_core_comment_model_generation_presets context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.model_generation_presets is
  'Reusable model generation presets controlling sampling and output limits for LLM requests.';

comment on column orac_core.model_generation_presets.model_preset_id is
  'Surrogate primary key for the model generation preset.';

comment on column orac_core.model_generation_presets.model_preset_code is
  'Unique short code identifying the model generation preset.';

comment on column orac_core.model_generation_presets.model_preset_name is
  'Display name for the model generation preset.';

comment on column orac_core.model_generation_presets.description is
  'Description of the preset intent and expected model-driving behaviour.';

comment on column orac_core.model_generation_presets.temperature is
  'Sampling temperature used by providers that support it.';

comment on column orac_core.model_generation_presets.top_p is
  'Nucleus sampling threshold used by providers that support it.';

comment on column orac_core.model_generation_presets.top_k is
  'Top-k sampling limit used by providers that support it.';

comment on column orac_core.model_generation_presets.repeat_penalty is
  'Repeat penalty used by providers that support it.';

comment on column orac_core.model_generation_presets.num_predict is
  'Requested maximum generated tokens, mapped per provider where supported.';

comment on column orac_core.model_generation_presets.seed is
  'Optional deterministic seed for providers that support seeded generation.';

comment on column orac_core.model_generation_presets.is_system_preset is
  'Indicates whether the preset is supplied by Orac rather than user-created.';

comment on column orac_core.model_generation_presets.is_active is
  'Indicates whether the preset is available for selection.';

comment on column orac_core.model_generation_presets.created_by is
  'User or process that created the row.';

comment on column orac_core.model_generation_presets.created_on is
  'Timestamp when the row was created.';

comment on column orac_core.model_generation_presets.updated_by is
  'User or process that last updated the row.';

comment on column orac_core.model_generation_presets.updated_on is
  'Timestamp when the row was last updated.';

comment on column orac_core.model_generation_presets.row_version is
  'Row version number used for optimistic locking.';
