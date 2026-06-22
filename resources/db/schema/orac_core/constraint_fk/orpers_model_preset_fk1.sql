--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_fk_orpers_model_preset_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'ORPERS_MODEL_PRESET_FK1';
-- __author__: clive
-- __date__: 2026-05-23
-- __description__: links Orac personalities to default model presets


alter table orac_core.orac_personalities
  add constraint orpers_model_preset_fk1
  foreign key (model_preset_id)
  references orac_core.model_generation_presets (model_preset_id)
;

--rollback alter table orac_core.orac_personalities drop constraint orpers_model_preset_fk1;
