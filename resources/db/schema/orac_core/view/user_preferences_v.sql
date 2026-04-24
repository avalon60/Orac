-- __author__: clive
-- __date__: 2026-04-24
-- __description__: generated/synchronised by split_ddl; one object per file


create or replace view orac.user_preferences_v as
select
  p.pref_id,
  p.user_id,
  p.pref_key,
  p.value_type,
  p.row_version,
  case p.value_type
    when 'string' then json_value(p.pref_value, '$' returning varchar2(4000) null on error)
    when 'number' then to_char(json_value(p.pref_value, '$' returning number null on error))
    when 'boolean' then lower(json_value(p.pref_value, '$' returning varchar2(5) null on error))
  end as value_display
from orac.user_preferences p
;
