-- __author__: clive
-- __date__: 2026-04-24
-- __description__: generated/synchronised by split_ddl; one object per file


create or replace view orac.token_usage_trend_v as
select
  trunc(m.created_on) as day,
  sum(m.tokens_used) as total_tokens
from orac.messages m
where m.tokens_used is not null
group by trunc(m.created_on)
order by day
;
