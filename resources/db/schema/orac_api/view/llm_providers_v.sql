--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Exposes the llm_providers API projection.

--changeset clive:create_view_orac_api_llm_providers_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.llm_providers_v as
select provider_code
     , display_name
     , adapter_class
     , processing_locality_domain_code
     , processing_locality_ref_value_code
     , metadata_status_domain_code
     , metadata_status_ref_value_code
     , effective_from
     , effective_to
     , native_properties
     , created_by
     , created_on
     , updated_by
     , updated_on
     , row_version
  from orac_core.llm_providers;
--rollback drop view orac_api.llm_providers_v;

