--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Grants the API layer controlled access to llm_input_media_types.

--changeset clive:grant_orac_core_llm_input_media_types_to_orac_api context:core labels:core stripComments:false runOnChange:true
grant select, insert, update, delete on orac_core.llm_input_media_types
  to orac_api with grant option;
--rollback revoke select, insert, update, delete on orac_core.llm_input_media_types from orac_api;

