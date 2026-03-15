-- __author__: clive bostock
-- __date__: 2025-10-19
-- __description__: generated/synchronised by Cline; one object per file

create or replace view orac.message_role_breakdown_v as
select
  m.role,
  count(*) as message_count
from orac.messages m
group by m.role;
