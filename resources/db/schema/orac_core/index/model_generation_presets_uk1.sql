-- __author__: clive
-- __date__: 2026-05-23
-- __description__: unique code index for model_generation_presets


create unique index orac_core.model_generation_presets_uk1
  on orac_core.model_generation_presets (model_preset_code)
;
