--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines a safe read projection for controlled LLM metadata.

--changeset clive:create_view_orac_code_llm_capability_catalogue_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.llm_capability_catalogue_v as
select capability_code
     , display_name
     , capability_class_ref_value_code capability_class
     , capability_lifecycle_ref_value_code capability_lifecycle
     , behaviour_summary
  from orac_api.llm_capabilities_v;
--rollback drop view orac_code.llm_capability_catalogue_v;

