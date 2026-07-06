--liquibase formatted sql

--changeset cbostock:home_assistant_constraint_uc_ha_entities_uk1 context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_HA' and constraint_name = 'HA_ENTITIES_UK1'
alter table orac_ha.ha_entities
  add constraint ha_entities_uk1
  unique (ha_entity_id)
  using index orac_ha.ha_entities_uk1_idx;

--rollback alter table orac_ha.ha_entities drop constraint ha_entities_uk1;
