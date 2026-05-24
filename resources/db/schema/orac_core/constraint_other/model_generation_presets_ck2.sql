-- __author__: clive
-- __date__: 2026-05-23
-- __description__: validates model_generation_presets active flag


alter table orac_core.model_generation_presets
  add constraint model_generation_presets_ck2
  check (is_active in ('Y', 'N'))
;
