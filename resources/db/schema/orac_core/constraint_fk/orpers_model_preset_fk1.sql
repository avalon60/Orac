-- __author__: clive
-- __date__: 2026-05-23
-- __description__: links Orac personalities to default model presets


alter table orac_core.orac_personalities
  add constraint orpers_model_preset_fk1
  foreign key (model_preset_id)
  references orac_core.model_generation_presets (model_preset_id)
;
