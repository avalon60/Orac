merge into orac_core.preference_definitions tgt
using (
  select
    'date_format' as pref_key,
    'Date Format' as display_label,
    'Preferred date and time display format for the user interface.' as description,
    'string' as value_type,
    'select_list' as control_type,
    'static' as lov_type,
    cast(null as varchar2(4000 byte)) as lov_query,
    'DATE_FORMAT' as static_lov_code,
    json(q'["DD-MON-YYYY HH24:MI"]') as default_value,
    cast(null as number) as min_number,
    cast(null as number) as max_number,
    5 as min_length,
    100 as max_length,
    cast(null as varchar2(1000 byte)) as regex_pattern,
    'Y' as is_required,
    'Y' as is_user_editable,
    10 as display_sequence,
    'ui' as category,
    'Controls how dates and times are rendered in reports and forms.' as help_text,
    'Y' as is_active
  from dual
  union all
  select
    'default_llm_id',
    'Default LLM',
    'Default LLM identifier used when no model is explicitly selected.',
    'number',
    'select_list',
    'sql',
    q'[select name || ' (' || provider || ')' d,
             to_char(llm_id) r
        from llm_registry_v
       where is_enabled = 'Y'
       order by provider, name]',
    cast(null as varchar2(100 byte)),
    json('0'),
    0,
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    20,
    'model',
    'Choose the model used by default for new requests.',
    'Y'
  from dual
  union all
  select
    'email_opt_in',
    'Email Notifications',
    'Whether the user wishes to receive email-based notifications.',
    'boolean',
    'checkbox',
    cast(null as varchar2(30 byte)),
    cast(null as varchar2(4000 byte)),
    cast(null as varchar2(100 byte)),
    json('true'),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    30,
    'notifications',
    'Enable or disable email notifications.',
    'Y'
  from dual
  union all
  select
    'enable_advanced_mode',
    'Advanced Mode',
    'Whether advanced UI and model controls are available to the user.',
    'boolean',
    'checkbox',
    cast(null as varchar2(30 byte)),
    cast(null as varchar2(4000 byte)),
    cast(null as varchar2(100 byte)),
    json('false'),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    40,
    'ui',
    'Enable additional controls intended for experienced users.',
    'Y'
  from dual
  union all
  select
    'enable_feedback',
    'Enable Feedback',
    'Whether the user interface should offer response feedback controls.',
    'boolean',
    'checkbox',
    cast(null as varchar2(30 byte)),
    cast(null as varchar2(4000 byte)),
    cast(null as varchar2(100 byte)),
    json('true'),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    50,
    'ui',
    'Show or hide feedback actions in the user interface.',
    'Y'
  from dual
  union all
  select
    'force_concise',
    'Force Concise Responses',
    'Whether responses should prefer concise phrasing by default.',
    'boolean',
    'checkbox',
    cast(null as varchar2(30 byte)),
    cast(null as varchar2(4000 byte)),
    cast(null as varchar2(100 byte)),
    json('true'),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    60,
    'model',
    'Biases Orac toward shorter answers unless the task requires more detail.',
    'Y'
  from dual
  union all
  select
    'landing_page_id',
    'Landing Page',
    'Default landing page shown when the user enters the application.',
    'number',
    'select_list',
    'sql',
    q'[select page_name || ' (' || page_id || ')' d,
             to_char(page_id) r
        from apex_application_pages
       where application_id = coalesce(
               to_number(nullif(sys_context('APEX$SESSION', 'APP_ID'), '')),
               1042
             )
         and page_id not in (0, 9999)
       order by page_id]',
    cast(null as varchar2(100 byte)),
    json('0'),
    0,
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    70,
    'ui',
    'Determines the default page opened for the user.',
    'Y'
  from dual
  union all
  select
    'max_tokens',
    'Max Tokens',
    'Default maximum token budget used for LLM responses.',
    'number',
    'number',
    cast(null as varchar2(30 byte)),
    cast(null as varchar2(4000 byte)),
    cast(null as varchar2(100 byte)),
    json('512'),
    1,
    32768,
    cast(null as number),
    cast(null as number),
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    80,
    'model',
    'Limits response size for supported models.',
    'Y'
  from dual
  union all
  select
    'push_opt_in',
    'Push Notifications',
    'Whether the user wishes to receive push notifications.',
    'boolean',
    'checkbox',
    cast(null as varchar2(30 byte)),
    cast(null as varchar2(4000 byte)),
    cast(null as varchar2(100 byte)),
    json('false'),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    90,
    'notifications',
    'Enable or disable push notifications.',
    'Y'
  from dual
  union all
  select
    'rows_per_report',
    'Rows Per Report',
    'Default number of rows shown in tabular report regions.',
    'number',
    'number',
    cast(null as varchar2(30 byte)),
    cast(null as varchar2(4000 byte)),
    cast(null as varchar2(100 byte)),
    json('50'),
    5,
    500,
    cast(null as number),
    cast(null as number),
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    100,
    'ui',
    'Controls the default pagination size for reports.',
    'Y'
  from dual
  union all
  select
    'show_reasoning',
    'Show Reasoning',
    'Whether reasoning content should be displayed when available.',
    'boolean',
    'checkbox',
    cast(null as varchar2(30 byte)),
    cast(null as varchar2(4000 byte)),
    cast(null as varchar2(100 byte)),
    json('false'),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    110,
    'reasoning',
    'Show internal reasoning content when a model provides it.',
    'Y'
  from dual
  union all
  select
    'strip_reasoning_tags',
    'Strip Reasoning Tags',
    'Whether reasoning markup tags should be removed from visible output.',
    'boolean',
    'checkbox',
    cast(null as varchar2(30 byte)),
    cast(null as varchar2(4000 byte)),
    cast(null as varchar2(100 byte)),
    json('true'),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    120,
    'reasoning',
    'Keeps visible output cleaner when reasoning markup is present.',
    'Y'
  from dual
  union all
  select
    'temperature',
    'Temperature',
    'Default temperature used for supported model requests.',
    'number',
    'number',
    cast(null as varchar2(30 byte)),
    cast(null as varchar2(4000 byte)),
    cast(null as varchar2(100 byte)),
    json('0.2'),
    0,
    2,
    cast(null as number),
    cast(null as number),
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    130,
    'model',
    'Lower values favour determinism; higher values favour variation.',
    'Y'
  from dual
  union all
  select
    'theme_style',
    'Theme Style',
    'Preferred application theme style.',
    'string',
    'select_list',
    'sql',
    q'[select name as style_name_display,
             name as style_name_return
        from apex_application_theme_styles
       where application_id = :APP_ID
         and is_public = 'Yes'
       order by case is_current
                  when 'Yes' then 0
                  else 1
                end,
                name]',
    cast(null as varchar2(100 byte)),
    json(q'["Vita"]'),
    cast(null as number),
    cast(null as number),
    1,
    100,
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    140,
    'ui',
    'Controls the overall application look and feel.',
    'Y'
  from dual
  union all
  select
    'weather_location',
    'Weather Location',
    'Default place used for weather questions when no explicit location is given.',
    'json',
    'select_one',
    'sql',
    q'~select jt.display_value d,
              jt.return_value r
         from json_table(
                orac_code.preference_lov_api.get_lov_json(
                  p_pref_key      => 'weather_location',
                  p_search        => :APEX$SEARCH,
                  p_current_value => null
                ),
                '$[*]'
                columns (
                  display_value varchar2(4000) path '$.display_value',
                  return_value varchar2(4000) path '$.return_value'
                )
              ) jt~',
    cast(null as varchar2(100 byte)),
    json('{"name":null,"latitude":null,"longitude":null,"timezone":null,"country":null,"admin1":null}'),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as number),
    cast(null as varchar2(1000 byte)),
    'N',
    'Y',
    145,
    'weather',
    'Stores the user''s preferred place for weather lookups and location-aware forecasts.',
    'Y'
  from dual
  union all
  select
    'timezone',
    'Timezone',
    'Default timezone used for date, time, and scheduling display.',
    'string',
    'select_list',
    'sql',
    q'[select display_label d, tz_name r
         from timezones_v
        where is_active = 'Y'
        order by region_group, display_sequence, display_label]',
    cast(null as varchar2(100 byte)),
    json(q'["Europe/London"]'),
    cast(null as number),
    cast(null as number),
    1,
    100,
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    150,
    'ui',
    'Used when rendering or interpreting date and time values for the user.',
    'Y'
  from dual
  union all
  select
    'tts_pitch',
    'TTS Pitch',
    'Default text-to-speech pitch setting.',
    'number',
    'number',
    cast(null as varchar2(30 byte)),
    cast(null as varchar2(4000 byte)),
    cast(null as varchar2(100 byte)),
    json('0'),
    -10,
    10,
    cast(null as number),
    cast(null as number),
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    160,
    'speech',
    'Controls pitch for supported text-to-speech playback.',
    'Y'
  from dual
  union all
  select
    'tts_rate',
    'TTS Rate',
    'Default text-to-speech playback rate.',
    'number',
    'number',
    cast(null as varchar2(30 byte)),
    cast(null as varchar2(4000 byte)),
    cast(null as varchar2(100 byte)),
    json('0.95'),
    0.25,
    4,
    cast(null as number),
    cast(null as number),
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    170,
    'speech',
    'Controls speech rate for supported text-to-speech playback.',
    'Y'
  from dual
  union all
  select
    'tts_voice',
    'TTS Voice',
    'Preferred text-to-speech voice.',
    'string',
    'select_list',
    'static',
    cast(null as varchar2(4000 byte)),
    'TTS_VOICE',
    json(q'["en-GB-female-1"]'),
    cast(null as number),
    cast(null as number),
    1,
    100,
    cast(null as varchar2(1000 byte)),
    'Y',
    'Y',
    180,
    'speech',
    'Chooses the default voice for supported text-to-speech playback.',
    'Y'
  from dual
) src
on (tgt.pref_key = src.pref_key)
when matched then update set
  tgt.display_label = src.display_label,
  tgt.description = src.description,
  tgt.value_type = src.value_type,
  tgt.control_type = src.control_type,
  tgt.lov_type = src.lov_type,
  tgt.lov_query = src.lov_query,
  tgt.static_lov_code = src.static_lov_code,
  tgt.default_value = src.default_value,
  tgt.min_number = src.min_number,
  tgt.max_number = src.max_number,
  tgt.min_length = src.min_length,
  tgt.max_length = src.max_length,
  tgt.regex_pattern = src.regex_pattern,
  tgt.is_required = src.is_required,
  tgt.is_user_editable = src.is_user_editable,
  tgt.display_sequence = src.display_sequence,
  tgt.category = src.category,
  tgt.help_text = src.help_text,
  tgt.is_active = src.is_active
when not matched then insert (
  pref_key,
  display_label,
  description,
  value_type,
  control_type,
  lov_type,
  lov_query,
  static_lov_code,
  default_value,
  min_number,
  max_number,
  min_length,
  max_length,
  regex_pattern,
  is_required,
  is_user_editable,
  display_sequence,
  category,
  help_text,
  is_active
) values (
  src.pref_key,
  src.display_label,
  src.description,
  src.value_type,
  src.control_type,
  src.lov_type,
  src.lov_query,
  src.static_lov_code,
  src.default_value,
  src.min_number,
  src.max_number,
  src.min_length,
  src.max_length,
  src.regex_pattern,
  src.is_required,
  src.is_user_editable,
  src.display_sequence,
  src.category,
  src.help_text,
  src.is_active
);
