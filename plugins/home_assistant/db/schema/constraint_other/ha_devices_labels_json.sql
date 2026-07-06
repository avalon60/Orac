--liquibase formatted sql

--changeset cbostock:home_assistant_constraint_other_ha_devices_labels_json context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_HA' and constraint_name = 'HA_DEVICES_LABELS_JSON'
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_ha.ha_devices
  add constraint ha_devices_labels_json
  check (labels is json);

--rollback alter table orac_ha.ha_devices drop constraint ha_devices_labels_json;
