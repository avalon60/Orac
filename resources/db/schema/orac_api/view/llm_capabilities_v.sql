--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Exposes the llm_capabilities API projection.

--changeset clive:create_view_orac_api_llm_capabilities_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.llm_capabilities_v as
select capability_code
     , display_name
     , capability_class_domain_code
     , capability_class_ref_value_code
     , capability_lifecycle_domain_code
     , capability_lifecycle_ref_value_code
     , behaviour_summary
     , created_by
     , created_on
     , updated_by
     , updated_on
     , row_version
  from orac_core.llm_capabilities;
--rollback drop view orac_api.llm_capabilities_v;

