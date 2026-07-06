--liquibase formatted sql

--changeset cbostock:home_assistant_constraint_other_ha_states_current_attributes_json context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_HA' and constraint_name = 'HA_STATES_CURRENT_ATTRIBUTES_JSON'
alter table orac_ha.ha_states_current
  add constraint ha_states_current_attributes_json
  check (attributes is json);

--rollback alter table orac_ha.ha_states_current drop constraint ha_states_current_attributes_json;
