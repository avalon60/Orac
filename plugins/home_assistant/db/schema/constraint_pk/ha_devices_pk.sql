--liquibase formatted sql

--changeset cbostock:home_assistant_constraint_pk_ha_devices_pk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_HA' and constraint_name = 'HA_DEVICES_PK'
alter table orac_ha.ha_devices
  add constraint ha_devices_pk
  primary key (device_id)
  using index orac_ha.ha_devices_pk_idx;

--rollback alter table orac_ha.ha_devices drop constraint ha_devices_pk;
