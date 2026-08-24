--liquibase formatted sql
-- Author: clive
-- Date: 23-Aug-2026
-- Description: Grants read-only metadata access to the Orac business layer.

--changeset clive:grant_read_orac_api_llm_model_cap_inputs_v_to_orac_code context:core labels:core stripComments:false runOnChange:true
grant read on orac_api.llm_model_cap_inputs_v to orac_code with grant option;
--rollback revoke read on orac_api.llm_model_cap_inputs_v from orac_code;

