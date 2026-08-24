--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Defines a safe read projection for controlled LLM metadata.

--changeset clive:create_view_orac_code_llm_provider_catalogue_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_code.llm_provider_catalogue_v as
select provider_code
     , display_name
     , adapter_class
     , processing_locality_ref_value_code processing_locality
     , metadata_status_ref_value_code metadata_status
     , effective_from
     , effective_to
  from orac_api.llm_providers_v;
--rollback drop view orac_code.llm_provider_catalogue_v;

