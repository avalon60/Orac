-- __author__: clive
-- __date__: 2026-05-23
-- __description__: unique code constraint for model_generation_presets


alter table orac_core.model_generation_presets
  add constraint model_generation_presets_uk1
  unique (model_preset_code)
;
