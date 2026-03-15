-- __author__: clive bostock
-- __date__: 2025-10-19
-- __description__: generated/synchronised by Cline; one object per file

create or replace view orac.messages_per_day_v as
select
  trunc(m.created_on) as day,
  count(*) as messages
from orac.messages m
group by trunc(m.created_on)
order by day;
