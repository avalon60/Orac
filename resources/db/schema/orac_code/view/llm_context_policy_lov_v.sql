--liquibase formatted sql

--changeset clive:create_view_orac_code_llm_context_policy_lov_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.llm_context_policy_lov_v as
select llm_context_policy_code return_value,
       display_value,
       description,
       display_sequence,
       icon,
       color
  from orac_code.llm_context_policy_v
 where domain_active_yn = 'Y'
   and active_yn = 'Y';
--rollback drop view orac_code.llm_context_policy_lov_v;
