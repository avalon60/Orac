-- __author__: clive bostock
-- __date__: 2025-10-19
-- __description__: generated/synchronised by Cline; one object per file

create or replace view orac.token_usage_trend_v as
select
  trunc(m.created_on) as day,
  sum(m.tokens_used) as total_tokens
from orac.messages m
where m.tokens_used is not null
group by trunc(m.created_on)
order by day;
