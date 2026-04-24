-- __author__: clive
-- __date__: 2026-04-24
-- __description__: generated/synchronised by split_ddl; one object per file


create or replace view orac.message_role_breakdown_v as
select
  m.role,
  count(*) as message_count
from orac.messages m
group by m.role
;
