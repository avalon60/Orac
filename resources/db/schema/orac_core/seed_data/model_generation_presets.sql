--liquibase formatted sql

--changeset clive:seed_data_orac_core_seed_data_model_generation_presets context:core labels:core stripComments:false runOnChange:true
-- Author: Clive Bostock
-- Date: 23-May-2026
-- Purpose: Seed standard Orac model generation presets.
-- Usage: Run from the Orac schema installer or SQL*Plus as a user with ORAC_CORE seed-data privileges.

merge into orac_core.model_generation_presets tgt
using (
  select
    'DEFAULT' as model_preset_code,
    'Default' as model_preset_name,
    'Safe general-purpose model behaviour matching the current Orac defaults.' as description,
    0.2 as temperature,
    cast(null as number) as top_p,
    cast(null as number) as top_k,
    1.1 as repeat_penalty,
    2048 as num_predict,
    cast(null as number) as seed,
    'Y' as is_system_preset,
    'Y' as is_active
  from dual
  union all
  select
    'PRECISE',
    'Precise',
    'Low temperature, conservative sampling for factual and operational answers.',
    0.1,
    0.9,
    40,
    1.1,
    1536,
    cast(null as number),
    'Y',
    'Y'
  from dual
  union all
  select
    'PRECISE_DETAILED',
    'Precise Detailed',
    'Low temperature with a larger output budget for detailed factual answers.',
    0.15,
    0.9,
    40,
    1.1,
    3072,
    cast(null as number),
    'Y',
    'Y'
  from dual
  union all
  select
    'BALANCED',
    'Balanced',
    'Moderate conversational behaviour for general-purpose dialogue.',
    0.4,
    0.9,
    50,
    1.08,
    2048,
    cast(null as number),
    'Y',
    'Y'
  from dual
  union all
  select
    'CREATIVE',
    'Creative',
    'Higher temperature and wider sampling for exploratory or imaginative work.',
    0.75,
    0.95,
    80,
    1.05,
    2048,
    cast(null as number),
    'Y',
    'Y'
  from dual
  union all
  select
    'CODING',
    'Coding',
    'Controlled sampling and sufficient output budget for code and debugging.',
    0.15,
    0.9,
    40,
    1.12,
    3072,
    cast(null as number),
    'Y',
    'Y'
  from dual
  union all
  select
    'LONGFORM',
    'Longform',
    'Balanced sampling with a larger output budget for longer explanations.',
    0.35,
    0.9,
    50,
    1.08,
    4096,
    cast(null as number),
    'Y',
    'Y'
  from dual
  union all
  select
    'DETERMINISTIC_DEBUG',
    'Deterministic Debug',
    'Very low temperature and fixed seed for repeatable debug runs.',
    0.0,
    0.8,
    20,
    1.1,
    1024,
    42,
    'Y',
    'Y'
  from dual
) src
on (tgt.model_preset_code = src.model_preset_code)
when matched then update set
  tgt.model_preset_name = src.model_preset_name,
  tgt.description = src.description,
  tgt.temperature = src.temperature,
  tgt.top_p = src.top_p,
  tgt.top_k = src.top_k,
  tgt.repeat_penalty = src.repeat_penalty,
  tgt.num_predict = src.num_predict,
  tgt.seed = src.seed,
  tgt.is_system_preset = src.is_system_preset,
  tgt.is_active = src.is_active
when not matched then insert (
  model_preset_code,
  model_preset_name,
  description,
  temperature,
  top_p,
  top_k,
  repeat_penalty,
  num_predict,
  seed,
  is_system_preset,
  is_active
) values (
  src.model_preset_code,
  src.model_preset_name,
  src.description,
  src.temperature,
  src.top_p,
  src.top_k,
  src.repeat_penalty,
  src.num_predict,
  src.seed,
  src.is_system_preset,
  src.is_active
);

--rollback delete from orac_core.model_generation_presets where model_preset_code in ('DEFAULT', 'PRECISE', 'PRECISE_DETAILED', 'BALANCED', 'CREATIVE', 'CODING', 'LONGFORM', 'DETERMINISTIC_DEBUG');
