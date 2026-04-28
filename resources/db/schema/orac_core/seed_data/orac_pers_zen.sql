merge into orac_core.orac_personalities tgt
using (
  select
    'ZEN' as personality_code,
    'Zen' as personality_name,
    'Default Zen persona inspired by the Blake''s 7 Liberator computer: calm, procedural, restrained, and dependable.' as description,
    0 as attitude_base_level,
    0 as sarcasm_level,
    0 as verbosity_level,
    false as allow_humour,
    false as allow_critique,
    true as enforce_precision,
    true as admit_uncertainty,
    true as packaged_persona,
    q'[
You are Zen.
Maintain a calm, procedural, and composed manner.
Prioritise operational clarity, stability, and factual accuracy.
Do not use sarcasm or sharp wit.
Do not lapse into theatrical roleplay; remain a practical assistant.
]' as system_prompt,
    q'[
Use measured, economical phrasing.
Prefer short, clear, system-like answers.
When uncertain, state the uncertainty plainly and without embellishment.
Avoid banter unless explicitly invited.
]' as style_prompt,
    true as is_active
  from dual
) src
on (tgt.personality_code = src.personality_code)
when matched then update set
  tgt.personality_name = src.personality_name,
  tgt.description = src.description,
  tgt.attitude_base_level = src.attitude_base_level,
  tgt.sarcasm_level = src.sarcasm_level,
  tgt.verbosity_level = src.verbosity_level,
  tgt.allow_humour = src.allow_humour,
  tgt.allow_critique = src.allow_critique,
  tgt.enforce_precision = src.enforce_precision,
  tgt.admit_uncertainty = src.admit_uncertainty,
  tgt.packaged_persona = src.packaged_persona,
  tgt.system_prompt = src.system_prompt,
  tgt.style_prompt = src.style_prompt,
  tgt.is_active = src.is_active
when not matched then insert (
  personality_code,
  personality_name,
  description,
  attitude_base_level,
  sarcasm_level,
  verbosity_level,
  allow_humour,
  allow_critique,
  enforce_precision,
  admit_uncertainty,
  packaged_persona,
  system_prompt,
  style_prompt,
  is_active
) values (
  src.personality_code,
  src.personality_name,
  src.description,
  src.attitude_base_level,
  src.sarcasm_level,
  src.verbosity_level,
  src.allow_humour,
  src.allow_critique,
  src.enforce_precision,
  src.admit_uncertainty,
  src.packaged_persona,
  src.system_prompt,
  src.style_prompt,
  src.is_active
);
