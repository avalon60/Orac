--liquibase formatted sql

--changeset clive:create_synonym_orac_apx_pub_synonym_model_generation_presets_v context:core labels:core stripComments:false runOnChange:true
create or replace synonym orac_apx_pub.model_generation_presets_v
  for orac_api.model_generation_presets_v;

--rollback drop synonym orac_apx_pub.model_generation_presets_v;
