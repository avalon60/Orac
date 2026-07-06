--liquibase formatted sql

--changeset cbostock:home_assistant_constraint_other_ha_areas_labels_json context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_HA' and constraint_name = 'HA_AREAS_LABELS_JSON'
alter table orac_ha.ha_areas
  add constraint ha_areas_labels_json
  check (labels is json);

--rollback alter table orac_ha.ha_areas drop constraint ha_areas_labels_json;
