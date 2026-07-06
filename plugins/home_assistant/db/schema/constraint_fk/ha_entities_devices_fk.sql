--liquibase formatted sql

--changeset cbostock:home_assistant_constraint_fk_ha_entities_devices_fk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_HA' and constraint_name = 'HA_ENTITIES_DEVICES_FK'
alter table orac_ha.ha_entities
  add constraint ha_entities_devices_fk
  foreign key
  (
    device_id
  )
  references orac_ha.ha_devices
  (
    device_id
  )
  not deferrable;

--rollback alter table orac_ha.ha_entities drop constraint ha_entities_devices_fk;
