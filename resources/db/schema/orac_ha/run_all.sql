set echo on

spool run_all.log

prompt === tables ===
@table/ha_areas.sql
@table/ha_devices.sql
@table/ha_entities.sql
@table/ha_states_current.sql

prompt === indexes ===
@index/ha_areas_pk_idx.sql
@index/ha_devices_area_id_idx.sql
@index/ha_devices_pk_idx.sql
@index/ha_entities_device_id_idx.sql
@index/ha_entities_pk_idx.sql
@index/ha_entities_uk1_idx.sql
@index/ha_states_current_pk_idx.sql
@index/ha_states_current_state_idx.sql

prompt === constraints_pk ===
@constraint_pk/ha_areas_pk.sql
@constraint_pk/ha_devices_pk.sql
@constraint_pk/ha_entities_pk.sql
@constraint_pk/ha_states_current_pk.sql

prompt === constraints_uc ===
@constraint_uc/ha_entities_uk1.sql

prompt === constraints_fk ===
@constraint_fk/ha_devices_areas_fk.sql
@constraint_fk/ha_entities_devices_fk.sql
@constraint_fk/ha_states_current_entities_fk.sql

prompt === constraints_other ===
@constraint_other/ha_areas_aliases_json.sql
@constraint_other/ha_areas_labels_json.sql
@constraint_other/ha_devices_cfg_subentries_json.sql
@constraint_other/ha_devices_config_entries_json.sql
@constraint_other/ha_devices_connections_json.sql
@constraint_other/ha_devices_identifiers_json.sql
@constraint_other/ha_devices_labels_json.sql
@constraint_other/ha_entities_categories_json.sql
@constraint_other/ha_entities_labels_json.sql
@constraint_other/ha_entities_options_json.sql
@constraint_other/ha_states_current_attributes_json.sql

spool off
