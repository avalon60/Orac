--liquibase formatted sql

--changeset cbostock:home_assistant_index_ha_areas_pk_idx context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_HA' and index_name = 'HA_AREAS_PK_IDX'
create unique index orac_ha.ha_areas_pk_idx
  on orac_ha.ha_areas
  (
    area_id asc
  )
logging;

--rollback drop index orac_ha.ha_areas_pk_idx;
