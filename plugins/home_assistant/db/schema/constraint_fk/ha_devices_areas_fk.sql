--liquibase formatted sql

--changeset cbostock:home_assistant_constraint_fk_ha_devices_areas_fk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_HA' and constraint_name = 'HA_DEVICES_AREAS_FK'
alter table orac_ha.ha_devices
  add constraint ha_devices_areas_fk
  foreign key
  (
    area_id
  )
  references orac_ha.ha_areas
  (
    area_id
  )
  not deferrable;

--rollback alter table orac_ha.ha_devices drop constraint ha_devices_areas_fk;
