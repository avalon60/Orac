--------------------------------------------------------------------------------
-- VIEWS
--------------------------------------------------------------------------------

-- view: messages_per_day_v — daily message counts (NOTE: ORDER BY in views is ignored at query time)
create or replace view orac.messages_per_day_v as
select
  trunc(m.created_on) as day,
  count(*) as messages
from orac.messages m
group by trunc(m.created_on)
order by day;

-- view: llm_usage_breakdown_v — message counts by conversation default llm
create or replace view orac.llm_usage_breakdown_v as
select
  l.name as model_name,
  count(*) as usage_count
from orac.messages m
join orac.conversations c on m.conversation_id = c.conversation_id
join orac.llm_registry l on c.llm_id = l.llm_id
group by l.name
order by usage_count desc;

-- view: token_usage_trend_v — total tokens per day (where tracked)
create or replace view orac.token_usage_trend_v as
select
  trunc(m.created_on) as day,
  sum(m.tokens_used) as total_tokens
from orac.messages m
where m.tokens_used is not null
group by trunc(m.created_on)
order by day;

-- view: message_role_breakdown_v — counts by role
create or replace view orac.message_role_breakdown_v as
select
  m.role,
  count(*) as message_count
from orac.messages m
group by m.role;

-- view: user_preferences_v — friendly projection with display-ready scalar (no quotes for strings)
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
