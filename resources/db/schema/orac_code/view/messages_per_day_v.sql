-- __author__: clive
-- __date__: 2026-04-25
-- __description__: daily message counts sourced via the API passthrough layer

create or replace view orac_code.messages_per_day_v as
select
  trunc(m.created_on) as day,
  count(*) as messages
from orac_api.messages_v m
group by trunc(m.created_on)
order by day;
