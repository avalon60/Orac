--liquibase formatted sql

--changeset clive:create_view_orac_api_view_users context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: published users view for POLP-compatible consumers

create or replace view orac_api.users as
select
  u.user_id,
  u.username,
  u.display_name,
  u.email,
  u.is_active,
  u.created_on,
  u.created_by,
  u.updated_on,
  u.updated_by,
  u.row_version
from orac_core.users u
;

--rollback drop view orac_api.users;
