--liquibase formatted sql

--changeset cbostock:home_assistant_constraint_other_ha_sync_runs_status_ck context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_HA' and constraint_name = 'HA_SYNC_RUNS_STATUS_CK'
alter table orac_ha.ha_sync_runs
  add constraint ha_sync_runs_status_ck
  check (status in ('running', 'complete', 'failed'));

--rollback alter table orac_ha.ha_sync_runs drop constraint ha_sync_runs_status_ck;
