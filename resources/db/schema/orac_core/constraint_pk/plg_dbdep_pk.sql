--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_pk_plg_dbdep_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_DBDEP_PK';
-- __author__: clive
-- __date__: 2026-06-03
-- __description__: primary key for plugin_db_deployments


alter table orac_core.plugin_db_deployments add constraint plg_dbdep_pk
  primary key (plugin_db_deployment_id)
;

--rollback alter table orac_core.plugin_db_deployments drop constraint plg_dbdep_pk;
