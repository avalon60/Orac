--liquibase formatted sql
-- Author: Clive Bostock
-- Date: 24-Oct-2026
-- Purpose: Register the OpenAI-compatible outbound inference runner.
-- Usage: Installed through orac_core/schemaController.xml during core deployment.

--changeset clive:p2_04_seed_openai_compatible_provider context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from orac_core.llm_providers where provider_code = 'openai_compatible';
insert into orac_core.llm_providers (
  provider_code, display_name, adapter_class,
  processing_locality_ref_value_code, metadata_status_ref_value_code
) values (
  'openai_compatible', 'OpenAI-compatible inference',
  'model.llm_connector.OpenAICompatibleConnector', 'UNKNOWN', 'REVIEWED'
);
--rollback delete from orac_core.llm_providers where provider_code = 'openai_compatible';
