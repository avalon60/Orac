--liquibase formatted sql
-- Author: clive
-- Date: 31-Aug-2026
-- Description: Grants controlled model-evidence writes to the business layer.

--changeset clive:grant_execute_llm_model_capabilities_tapi_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant execute on orac_api.llm_model_capabilities_tapi to orac_code;
--rollback revoke execute on orac_api.llm_model_capabilities_tapi from orac_code;
