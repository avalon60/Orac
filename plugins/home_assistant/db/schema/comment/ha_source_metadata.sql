--liquibase formatted sql

--changeset cbostock:home_assistant_comment_ha_source_metadata context:plugin,prod labels:plugin,home_assistant stripComments:false runOnChange:true
comment on column orac_ha.ha_areas.ha_created_at is 'Home Assistant source created_at timestamp copied from the structural area payload.'
;
comment on column orac_ha.ha_areas.ha_modified_at is 'Home Assistant source modified_at timestamp copied from the structural area payload.'
;
comment on column orac_ha.ha_devices.ha_created_at is 'Home Assistant source created_at timestamp copied from the structural device payload.'
;
comment on column orac_ha.ha_devices.ha_modified_at is 'Home Assistant source modified_at timestamp copied from the structural device payload.'
;
comment on column orac_ha.ha_entities.ha_created_at is 'Home Assistant source created_at timestamp copied from the structural entity payload.'
;
comment on column orac_ha.ha_entities.ha_modified_at is 'Home Assistant source modified_at timestamp copied from the structural entity payload.'
;
