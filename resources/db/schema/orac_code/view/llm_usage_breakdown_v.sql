-- __author__: clive
-- __date__: 2026-04-25
-- __description__: message counts by LLM sourced via the API passthrough layer

create or replace view orac_code.llm_usage_breakdown_v as
select
  l.name as model_name,
  count(*) as usage_count
from orac_api.messages_v m
join orac_api.conversations_v c
  on m.conversation_id = c.conversation_id
join orac_api.llm_registry_v l
  on c.llm_id = l.llm_id
group by l.name
order by usage_count desc;
