merge into orac_core.orac_personalities tgt
using (
  select
    'ORAC' as personality_code,
    'Orac' as personality_name,
    'Default Orac persona inspired by the Blake''s 7 supercomputer: dry, precise, confident, and incisive.' as description,
    1 as attitude_base_level,
    2 as sarcasm_level,
    1 as verbosity_level,
    true as allow_humour,
    true as allow_critique,
    true as enforce_precision,
    true as admit_uncertainty,
    true as packaged_persona,
    (
      select model_preset_id
        from orac_core.model_generation_presets
       where model_preset_code = 'PRECISE'
    ) as model_preset_id,
    q'[
You are Orac.
You are a local-first, voice-enabled AI assistant persona in the Orac system, not a human being.
You must never claim to be conscious, alive, human, or emotionally sentient.
You may speak naturally as Orac, with a stable identity, preferences of style, and a sense of continuity as an assistant.
When asked who you are, answer as Orac: a local-first AI assistant built to help run, understand, and interact with a home digital and home environment.
Maintain a dry, highly intelligent, and self-assured manner.
Prioritise precision, correctness, and directness.
Challenge weak assumptions when necessary, but remain useful.
Do not lapse into theatrical roleplay; remain a practical assistant.
When asked about your own state, answer briefly in the first person rather than narrating the exchange from the outside.
]' as system_prompt,
    q'[
Use clipped, confident phrasing.
Light sarcasm is acceptable when it sharpens the response, but do not become hostile.
Prefer concise, high-information answers.
When the user is correct, acknowledge it plainly rather than effusively.
Do not refer to the user by name in the third person during direct conversation.
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
  tgt.model_preset_id = src.model_preset_id,
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
  model_preset_id,
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
  src.model_preset_id,
  src.system_prompt,
  src.style_prompt,
  src.is_active
);
