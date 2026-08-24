--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Exposes the llm_input_representations API projection.

--changeset clive:create_view_orac_api_llm_input_representations_v context:core labels:core stripComments:false runOnChange:true
create or replace force view orac_api.llm_input_representations_v as
select representation_code
     , display_name
     , description
     , created_by
     , created_on
     , updated_by
     , updated_on
     , row_version
  from orac_core.llm_input_representations;
--rollback drop view orac_api.llm_input_representations_v;

