--liquibase formatted sql

--changeset clive:create_view_orac_code_view_user_preferences_v context:core labels:core stripComments:false runOnChange:true
-- __author__: clive
-- __date__: 2026-04-26
-- __description__: APEX-facing maintenance view for user preferences

create or replace view orac_code.user_preferences_v as
select
  p.pref_id,
  p.user_id,
  p.pref_key,
  p.pref_value,
  p.value_type,
  p.created_on,
  p.created_by,
  p.updated_on,
  p.updated_by,
  p.row_version
from orac_api.user_preferences_v p
;

--rollback drop view orac_code.user_preferences_v;
