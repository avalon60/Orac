--liquibase formatted sql

--changeset clive:create_index_orac_core_index_plg_dbdep_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PLG_DBDEP_PK';
-- __author__: clive
-- __date__: 2026-06-03
-- __description__: primary key index for plugin_db_deployments


create unique index orac_core.plg_dbdep_pk
  on orac_core.plugin_db_deployments
     (plugin_db_deployment_id)
;

--rollback drop index orac_core.plg_dbdep_pk;
