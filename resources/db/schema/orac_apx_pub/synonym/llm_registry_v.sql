--liquibase formatted sql

--changeset clive:create_synonym_orac_apx_pub_synonym_llm_registry_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: public-facing llm registry view synonym

create or replace synonym orac_apx_pub.llm_registry_v for orac_api.llm_registry_v;

--rollback drop synonym orac_apx_pub.llm_registry_v;
