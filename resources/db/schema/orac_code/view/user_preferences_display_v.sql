--liquibase formatted sql

--changeset clive:create_view_orac_code_view_user_preferences_display_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: published user preferences projection

create or replace view orac_code.user_preferences_display_v as
select
  p.pref_id,
  p.user_id,
  p.pref_key,
  p.value_type,
  p.row_version,
  coalesce(d.is_active, 'N') as is_active,
  coalesce(d.is_user_editable, 'N') as is_user_editable,
  d.display_sequence,
  case
    when p.pref_key = 'user_location' then
      case
        when json_value(p.pref_value, '$.name' returning varchar2(4000) null on error) is not null then
          json_value(p.pref_value, '$.name' returning varchar2(4000) null on error)
          || case
               when json_value(p.pref_value, '$.admin1' returning varchar2(4000) null on error) is not null then
                 ', ' || json_value(p.pref_value, '$.admin1' returning varchar2(4000) null on error)
             end
          || case
               when json_value(p.pref_value, '$.country' returning varchar2(4000) null on error) is not null then
                 ', ' || json_value(p.pref_value, '$.country' returning varchar2(4000) null on error)
             end
      end
    when p.pref_key = 'default_llm_id' then
      coalesce(
        (
          select r.name
                 || ' ('
                 || r.provider
                 || ')'
                 || case
                      when nvl(r.is_enabled, 'N') <> 'Y' then
                        ' [disabled]'
                    end
            from orac_api.llm_registry_v r
           where r.llm_id = json_value(p.pref_value, '$' returning number null on error)
        )
      , to_char(json_value(p.pref_value, '$' returning number null on error))
      )
    when p.pref_key = 'tts_voice' then
      coalesce(
        (
          select initcap(v.provider_code)
                 || ' - '
                 || v.display_name
                 || ' ('
                 || v.provider_voice_id
                 || case
                      when v.locale_code is not null then
                        ', ' || v.locale_code
                    end
                 || case
                      when v.voice_quality is not null then
                        ', ' || v.voice_quality
                    end
                 || ')'
            from orac_api.tts_voices_v v
           where v.tts_voice_key = json_value(p.pref_value, '$' returning varchar2(300) null on error)
        )
      , json_value(p.pref_value, '$' returning varchar2(4000) null on error)
      )
    when p.value_type = 'string' then
      json_value(p.pref_value, '$' returning varchar2(4000) null on error)
    when p.value_type = 'number' then
      to_char(json_value(p.pref_value, '$' returning number null on error))
    when p.value_type = 'boolean' then
      lower(json_value(p.pref_value, '$' returning varchar2(5) null on error))
    when p.value_type = 'json' then
      json_serialize(p.pref_value returning varchar2(4000) null on error)
  end as value_display,
  coalesce(d.display_label, p.pref_key) as pref_label
from orac_api.user_preferences_v p
left join orac_api.preference_definitions_v d
  on d.pref_key = p.pref_key
;

--rollback drop view orac_code.user_preferences_display_v;
