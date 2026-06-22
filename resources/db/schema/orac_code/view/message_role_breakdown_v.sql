--liquibase formatted sql

--changeset clive:create_view_orac_code_view_message_role_breakdown_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: message counts by role sourced via the API passthrough layer

create or replace view orac_code.message_role_breakdown_v as
select
  m.role,
  count(*) as message_count
from orac_api.messages_v m
group by m.role;

--rollback drop view orac_code.message_role_breakdown_v;
