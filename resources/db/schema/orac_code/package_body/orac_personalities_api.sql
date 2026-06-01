-- __author__: clive
-- __date__: 2026-04-29
-- __description__: ORAC_CODE wrapper API for Orac personality maintenance

create or replace package body orac_code.orac_personalities_api as
  procedure ins(
    p_personality_id      in out orac_api.orac_personalities_v.personality_id%type,
    p_personality_code    in     orac_api.orac_personalities_v.personality_code%type,
    p_personality_name    in     orac_api.orac_personalities_v.personality_name%type,
    p_description         in     orac_api.orac_personalities_v.description%type,
    p_attitude_base_level in     orac_api.orac_personalities_v.attitude_base_level%type,
    p_sarcasm_level       in     orac_api.orac_personalities_v.sarcasm_level%type,
    p_verbosity_level     in     orac_api.orac_personalities_v.verbosity_level%type,
    p_allow_humour        in     orac_api.orac_personalities_v.allow_humour%type,
    p_allow_critique      in     orac_api.orac_personalities_v.allow_critique%type,
    p_enforce_precision   in     orac_api.orac_personalities_v.enforce_precision%type,
    p_admit_uncertainty   in     orac_api.orac_personalities_v.admit_uncertainty%type,
    p_packaged_persona    in     orac_api.orac_personalities_v.packaged_persona%type,
    p_model_preset_id     in     orac_api.orac_personalities_v.model_preset_id%type,
    p_system_prompt       in     orac_api.orac_personalities_v.system_prompt%type,
    p_style_prompt        in     orac_api.orac_personalities_v.style_prompt%type,
    p_is_active           in     orac_api.orac_personalities_v.is_active%type,
    p_row_version            out orac_api.orac_personalities_v.row_version%type
  ) as
  begin
    orac_api.orac_personalities_tapi.ins(
      p_personality_code    => p_personality_code,
      p_personality_name    => p_personality_name,
      p_description         => p_description,
      p_attitude_base_level => p_attitude_base_level,
      p_sarcasm_level       => p_sarcasm_level,
      p_verbosity_level     => p_verbosity_level,
      p_allow_humour        => p_allow_humour,
      p_allow_critique      => p_allow_critique,
      p_enforce_precision   => p_enforce_precision,
      p_admit_uncertainty   => p_admit_uncertainty,
      p_packaged_persona    => p_packaged_persona,
      p_model_preset_id     => p_model_preset_id,
      p_system_prompt       => p_system_prompt,
      p_style_prompt        => p_style_prompt,
      p_is_active           => p_is_active,
      p_row_version         => p_row_version
    );
  end ins;

  procedure upd(
    p_personality_id      in out orac_api.orac_personalities_v.personality_id%type,
    p_personality_code    in     orac_api.orac_personalities_v.personality_code%type,
    p_personality_name    in     orac_api.orac_personalities_v.personality_name%type,
    p_description         in     orac_api.orac_personalities_v.description%type,
    p_attitude_base_level in     orac_api.orac_personalities_v.attitude_base_level%type,
    p_sarcasm_level       in     orac_api.orac_personalities_v.sarcasm_level%type,
    p_verbosity_level     in     orac_api.orac_personalities_v.verbosity_level%type,
    p_allow_humour        in     orac_api.orac_personalities_v.allow_humour%type,
    p_allow_critique      in     orac_api.orac_personalities_v.allow_critique%type,
    p_enforce_precision   in     orac_api.orac_personalities_v.enforce_precision%type,
    p_admit_uncertainty   in     orac_api.orac_personalities_v.admit_uncertainty%type,
    p_packaged_persona    in     orac_api.orac_personalities_v.packaged_persona%type,
    p_model_preset_id     in     orac_api.orac_personalities_v.model_preset_id%type,
    p_system_prompt       in     orac_api.orac_personalities_v.system_prompt%type,
    p_style_prompt        in     orac_api.orac_personalities_v.style_prompt%type,
    p_is_active           in     orac_api.orac_personalities_v.is_active%type,
    p_row_version            out orac_api.orac_personalities_v.row_version%type
  ) as
  begin
    orac_api.orac_personalities_tapi.upd(
      p_personality_id      => p_personality_id,
      p_personality_code    => p_personality_code,
      p_personality_name    => p_personality_name,
      p_description         => p_description,
      p_attitude_base_level => p_attitude_base_level,
      p_sarcasm_level       => p_sarcasm_level,
      p_verbosity_level     => p_verbosity_level,
      p_allow_humour        => p_allow_humour,
      p_allow_critique      => p_allow_critique,
      p_enforce_precision   => p_enforce_precision,
      p_admit_uncertainty   => p_admit_uncertainty,
      p_packaged_persona    => p_packaged_persona,
      p_model_preset_id     => p_model_preset_id,
      p_system_prompt       => p_system_prompt,
      p_style_prompt        => p_style_prompt,
      p_is_active           => p_is_active,
      p_row_version         => p_row_version
    );
  end upd;

  procedure del(
    p_personality_id      in out orac_api.orac_personalities_v.personality_id%type,
    p_row_version            out orac_api.orac_personalities_v.row_version%type
  ) as
  begin
    orac_api.orac_personalities_tapi.del(
      p_personality_id => p_personality_id,
      p_row_version    => p_row_version
    );
  end del;
end orac_personalities_api;
/
