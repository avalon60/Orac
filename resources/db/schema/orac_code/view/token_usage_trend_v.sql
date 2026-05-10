-- __author__: clive
-- __date__: 2026-04-25
-- __description__: token usage trend sourced via the API passthrough layer

create or replace view orac_code.token_usage_trend_v as
select
  trunc(m.created_on) as day,
  to_char(trunc(m.created_on), 'DD Mon') as day_label,
  sum(m.tokens_used) as total_tokens
from orac_api.messages_v m
where m.tokens_used is not null
group by trunc(m.created_on)
order by day;
