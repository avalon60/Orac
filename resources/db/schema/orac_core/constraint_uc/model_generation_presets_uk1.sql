--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_uc_model_generation_presets_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'MODEL_GENERATION_PRESETS_UK1';
-- __author__: clive
-- __date__: 2026-05-23
-- __description__: unique code constraint for model_generation_presets


alter table orac_core.model_generation_presets
  add constraint model_generation_presets_uk1
  unique (model_preset_code)
;

--rollback alter table orac_core.model_generation_presets drop constraint model_generation_presets_uk1;
