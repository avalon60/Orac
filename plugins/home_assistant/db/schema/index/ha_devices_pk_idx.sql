--liquibase formatted sql

--changeset cbostock:home_assistant_index_ha_devices_pk_idx context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_HA' and index_name = 'HA_DEVICES_PK_IDX'
create unique index orac_ha.ha_devices_pk_idx
  on orac_ha.ha_devices
  (
    device_id asc
  )
logging;

--rollback drop index orac_ha.ha_devices_pk_idx;
