--liquibase formatted sql

--changeset cbostock:home_assistant_index_ha_entities_device_id_idx context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_HA' and index_name = 'HA_ENTITIES_DEVICE_ID_IDX'
create index orac_ha.ha_entities_device_id_idx
  on orac_ha.ha_entities
  (
    device_id asc
  )
logging;

--rollback drop index orac_ha.ha_entities_device_id_idx;
