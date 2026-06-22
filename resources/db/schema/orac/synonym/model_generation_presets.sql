--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_model_generation_presets context:core labels:core stripComments:false runOnChange:true
create or replace synonym orac.model_generation_presets
  for orac_api.model_generation_presets_v;

--rollback drop synonym orac.model_generation_presets;
