--liquibase formatted sql

--changeset cbostock:home_assistant_constraint_pk_ha_sync_runs_pk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_HA' and constraint_name = 'HA_SYNC_RUNS_PK'
alter table orac_ha.ha_sync_runs
  add constraint ha_sync_runs_pk
  primary key (sync_run_id)
  using index orac_ha.ha_sync_runs_pk_idx;

--rollback alter table orac_ha.ha_sync_runs drop constraint ha_sync_runs_pk;
