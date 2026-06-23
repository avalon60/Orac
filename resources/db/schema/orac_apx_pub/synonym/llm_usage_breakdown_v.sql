--liquibase formatted sql

--changeset clive:create_synonym_orac_apx_pub_synonym_llm_usage_breakdown_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: public-facing LLM usage breakdown view synonym

create or replace synonym orac_apx_pub.llm_usage_breakdown_v for orac_code.llm_usage_breakdown_v;

--rollback drop synonym orac_apx_pub.llm_usage_breakdown_v;
