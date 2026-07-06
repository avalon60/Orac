--liquibase formatted sql

--changeset cbostock:home_assistant_constraint_other_ha_entities_options_json context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_HA' and constraint_name = 'HA_ENTITIES_OPTIONS_JSON'
alter table orac_ha.ha_entities
  add constraint ha_entities_options_json
  check (options is json);

--rollback alter table orac_ha.ha_entities drop constraint ha_entities_options_json;
