--liquibase formatted sql

--changeset cbostock:home_assistant_constraint_pk_ha_states_current_pk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_HA' and constraint_name = 'HA_STATES_CURRENT_PK'
alter table orac_ha.ha_states_current
  add constraint ha_states_current_pk
  primary key (entity_id)
  using index orac_ha.ha_states_current_pk_idx;

--rollback alter table orac_ha.ha_states_current drop constraint ha_states_current_pk;
