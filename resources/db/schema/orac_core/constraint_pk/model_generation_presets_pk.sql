-- __author__: clive
-- __date__: 2026-05-23
-- __description__: primary key constraint for model_generation_presets


alter table orac_core.model_generation_presets
  add constraint model_generation_presets_pk
  primary key (model_preset_id)
;
