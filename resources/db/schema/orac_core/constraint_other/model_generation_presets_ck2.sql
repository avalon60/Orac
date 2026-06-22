--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_model_generation_presets_ck2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'MODEL_GENERATION_PRESETS_CK2';
-- __author__: clive
-- __date__: 2026-05-23
-- __description__: validates model_generation_presets active flag


alter table orac_core.model_generation_presets
  add constraint model_generation_presets_ck2
  check (is_active in ('Y', 'N'))
;

--rollback alter table orac_core.model_generation_presets drop constraint model_generation_presets_ck2;
