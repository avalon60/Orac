alter table plugins_core.ha_states_current
  add constraint ha_states_current_attributes_json
  check (attributes is json)
;
