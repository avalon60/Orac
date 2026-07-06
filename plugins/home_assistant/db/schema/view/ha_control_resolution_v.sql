--liquibase formatted sql

--changeset cbostock:home_assistant_view_ha_control_resolution_v context:plugin,prod labels:plugin,home_assistant stripComments:false runOnChange:true
-- orac-expected-columns: alias_name, entity_id, domain, object_id, entity_name
-- orac-expected-columns: original_name, disabled_by, friendly_name, device_class
-- orac-expected-columns: unit_of_measurement, device_name, effective_area_id
-- orac-expected-columns: area_name, area_aliases, current_state, last_changed, last_updated
create or replace view orac_ha.ha_control_resolution_v as
select dal.alias_name,
       ent.entity_id,
       regexp_substr(ent.entity_id, '^[^.]+') domain,
       substr(ent.entity_id, instr(ent.entity_id, '.') + 1) object_id,
       ent.name entity_name,
       ent.original_name,
       ent.disabled_by,
       json_value(sta.attributes, '$.friendly_name') friendly_name,
       json_value(sta.attributes, '$.device_class') device_class,
       json_value(sta.attributes, '$.unit_of_measurement') unit_of_measurement,
       coalesce(dev.name_by_user, dev.name) device_name,
       coalesce(ent.area_id, dev.area_id) effective_area_id,
       area.name area_name,
       area.aliases area_aliases,
       sta.state current_state,
       sta.last_changed,
       sta.last_updated
  from orac_ha.ha_entities ent
  left join orac_ha.ha_devices dev
    on dev.device_id = ent.device_id
  left join orac_ha.ha_areas area
    on area.area_id = coalesce(ent.area_id, dev.area_id)
  left join orac_ha.ha_states_current sta
    on sta.entity_id = ent.entity_id
  left join orac_ha.device_aliases dal
    on dal.entity_id = ent.entity_id
   and dal.enabled_flag = 'Y'
;
