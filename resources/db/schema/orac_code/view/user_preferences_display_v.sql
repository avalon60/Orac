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
  case
    when p.pref_key = 'weather_location' then
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
    when p.value_type = 'string' then
      json_value(p.pref_value, '$' returning varchar2(4000) null on error)
    when p.value_type = 'number' then
      to_char(json_value(p.pref_value, '$' returning number null on error))
    when p.value_type = 'boolean' then
      lower(json_value(p.pref_value, '$' returning varchar2(5) null on error))
    when p.value_type = 'json' then
      json_serialize(p.pref_value returning varchar2(4000) null on error)
  end as value_display
from orac_api.user_preferences_v p
;
