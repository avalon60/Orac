--liquibase formatted sql

--changeset cbostock:home_assistant_constraint_other_ha_devices_cfg_subentries_json context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_HA' and constraint_name = 'HA_DEVICES_CFG_SUBENTRIES_JSON'
alter table orac_ha.ha_devices
  add constraint ha_devices_cfg_subentries_json
  check (config_entries_subentries is json);

--rollback alter table orac_ha.ha_devices drop constraint ha_devices_cfg_subentries_json;
