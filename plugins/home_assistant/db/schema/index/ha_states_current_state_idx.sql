--liquibase formatted sql

--changeset cbostock:home_assistant_index_ha_states_current_state_idx context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_HA' and index_name = 'HA_STATES_CURRENT_STATE_IDX'
create index orac_ha.ha_states_current_state_idx
  on orac_ha.ha_states_current
  (
    state asc
  )
logging;

--rollback drop index orac_ha.ha_states_current_state_idx;
