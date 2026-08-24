--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Exposes the llm_input_media_types API projection.

--changeset clive:create_view_orac_api_llm_input_media_types_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.llm_input_media_types_v as
select media_type
     , display_name
     , mime_match_kind_domain_code
     , mime_match_kind_ref_value_code
     , description
     , created_by
     , created_on
     , updated_by
     , updated_on
     , row_version
  from orac_core.llm_input_media_types;
--rollback drop view orac_api.llm_input_media_types_v;

