-- __author__: clive
-- __date__: 2026-05-23
-- __description__: validates model_generation_presets system preset flag


alter table orac_core.model_generation_presets
  add constraint model_generation_presets_ck1
  check (is_system_preset in ('Y', 'N'))
;
