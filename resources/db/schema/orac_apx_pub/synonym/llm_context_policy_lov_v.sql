--liquibase formatted sql

--changeset clive:create_synonym_orac_apx_pub_llm_context_policy_lov_v context:core labels:core stripComments:false runOnChange:true
create or replace synonym orac_apx_pub.llm_context_policy_lov_v
  for orac_code.llm_context_policy_lov_v;
--rollback drop synonym orac_apx_pub.llm_context_policy_lov_v;
