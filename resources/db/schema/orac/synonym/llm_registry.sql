--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_llm_registry context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: compatibility synonym for legacy llm registry access

create or replace synonym orac.llm_registry for orac_api.llm_registry_v;

--rollback drop synonym orac.llm_registry;
