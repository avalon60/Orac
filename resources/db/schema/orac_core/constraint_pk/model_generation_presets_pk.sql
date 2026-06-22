--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_pk_model_generation_presets_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'MODEL_GENERATION_PRESETS_PK';
-- __author__: clive
-- __date__: 2026-05-23
-- __description__: primary key constraint for model_generation_presets


alter table orac_core.model_generation_presets
  add constraint model_generation_presets_pk
  primary key (model_preset_id)
;

--rollback alter table orac_core.model_generation_presets drop constraint model_generation_presets_pk;
