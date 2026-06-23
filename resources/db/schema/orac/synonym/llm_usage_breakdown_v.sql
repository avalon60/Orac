--liquibase formatted sql

--changeset clive:create_synonym_orac_synonym_llm_usage_breakdown_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: internal LLM usage breakdown view synonym

create or replace synonym orac.llm_usage_breakdown_v for orac_code.llm_usage_breakdown_v;

--rollback drop synonym orac.llm_usage_breakdown_v;
