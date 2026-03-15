-- __author__: clive bostock
-- __date__: 2025-10-19
-- __description__: generated/synchronised by Cline; one object per file

create or replace view orac.llm_usage_breakdown_v as
select
  l.name as model_name,
  count(*) as usage_count
from orac.messages m
join orac.conversations c on m.conversation_id = c.conversation_id
join orac.llm_registry l on c.llm_id = l.llm_id
group by l.name
order by usage_count desc;
