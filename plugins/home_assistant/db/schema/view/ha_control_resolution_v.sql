create or replace view orac_ha.ha_control_resolution_v as
select dal.alias_name,
       ent.entity_id,
       regexp_substr(ent.entity_id, '^[^.]+') domain,
       substr(ent.entity_id, instr(ent.entity_id, '.') + 1) object_id,
       ent.name entity_name,
       ent.original_name,
       json_value(sta.attributes, '$.friendly_name') friendly_name,
       coalesce(dev.name_by_user, dev.name) device_name,
       coalesce(ent.area_id, dev.area_id) effective_area_id,
       area.name area_name,
       area.aliases area_aliases,
       sta.state current_state
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
