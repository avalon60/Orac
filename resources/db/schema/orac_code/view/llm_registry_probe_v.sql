--liquibase formatted sql

--changeset clive:create_view_orac_code_view_llm_registry_probe_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-05-24
-- __description__: registered LLM reporting projection including probe metadata

create or replace view orac_code.llm_registry_probe_v as
select
  llm_id,
  name,
  provider,
  model,
  context_policy,
  max_context_tokens,
  is_enabled,
  json_value(
    properties,
    '$.service_url' returning varchar2(4000) null on error
  ) as service_url,
  json_value(
    properties,
    '$.size_bytes' returning number null on error
  ) as size_bytes,
  json_value(
    properties,
    '$.size_mb' returning number null on error
  ) as size_mb,
  case
    when json_value(properties, '$.size_mb' returning number null on error) is not null then
      to_char(
        json_value(properties, '$.size_mb' returning number null on error),
        'fm999g999g999g990d00'
      )
  end as size_mb_display,
  json_value(
    properties,
    '$.parameter_size' returning varchar2(100) null on error
  ) as parameter_size,
  json_value(
    properties,
    '$.quantization_level' returning varchar2(100) null on error
  ) as quantization_level,
  json_value(
    properties,
    '$.history_probe_status' returning varchar2(100) null on error
  ) as history_probe_status,
  json_value(
    properties,
    '$.supports_provider_history' returning varchar2(1) null on error
  ) as supports_provider_history,
  json_value(
    properties,
    '$.history_probe_suggested_context_policy' returning varchar2(20) null on error
  ) as suggested_context_policy,
  json_value(
    properties,
    '$.history_probe_checked_on' returning varchar2(40) null on error
  ) as history_probe_checked_on,
  json_value(
    properties,
    '$.history_probe_first_response_ms' returning number null on error
  ) as first_response_ms,
  json_value(
    properties,
    '$.history_probe_second_response_ms' returning number null on error
  ) as second_response_ms,
  json_value(
    properties,
    '$.history_probe_total_response_ms' returning number null on error
  ) as total_response_ms,
  json_value(
    properties,
    '$.history_probe_responsiveness_class' returning varchar2(30) null on error
  ) as responsiveness_class,
  json_value(
    properties,
    '$.history_probe_first_reply' returning varchar2(4000) null on error
  ) as first_reply,
  json_value(
    properties,
    '$.history_probe_second_reply' returning varchar2(4000) null on error
  ) as second_reply
from orac_api.llm_registry_v;

--rollback drop view orac_code.llm_registry_probe_v;
