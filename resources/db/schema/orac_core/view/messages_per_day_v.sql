-- __author__: clive
-- __date__: 2026-04-24
-- __description__: generated/synchronised by split_ddl; one object per file


create or replace view orac.messages_per_day_v as
select
  trunc(m.created_on) as day,
  count(*) as messages
from orac.messages m
group by trunc(m.created_on)
order by day
;
