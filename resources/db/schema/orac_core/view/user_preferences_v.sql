-- __author__: clive bostock
-- __date__: 2025-10-19
-- __description__: generated/synchronised by Cline; one object per file

create or replace view orac.user_preferences_v as
select
  p.pref_id,                 -- primary key (unique, not null)
  p.user_id,
  p.pref_key,
  p.value_type,              -- 'string' | 'number' | 'boolean'
  p.row_version,             -- for optimistic locking in APEX (optional but nice)
  /* Human-friendly value with quotes removed for strings */
  case p.value_type
    when 'string'  then json_value(p.pref_value, '$' returning varchar2(4000) null on error)
    when 'number'  then to_char(json_value(p.pref_value, '$' returning number         null on error))
    when 'boolean' then lower(json_value(p.pref_value, '$' returning varchar2(5)     null on error))
  end as value_display
from orac.user_preferences p;
