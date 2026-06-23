--liquibase formatted sql

--changeset clive:create_index_orac_core_index_model_generation_presets_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'MODEL_GENERATION_PRESETS_PK';
-- __author__: clive
-- __date__: 2026-05-23
-- __description__: primary key index for model_generation_presets


create unique index orac_core.model_generation_presets_pk
  on orac_core.model_generation_presets (model_preset_id)
;

--rollback drop index orac_core.model_generation_presets_pk;
