--liquibase formatted sql

--changeset clive:create_index_orac_core_index_plg_dbdep_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PLG_DBDEP_UK1_IDX';
-- __author__: clive
-- __date__: 2026-06-03
-- __description__: unique deployment checksum index for plugin_db_deployments


create unique index orac_core.plg_dbdep_uk1_idx
  on orac_core.plugin_db_deployments
     (plugin_id, plugin_version, schema_name, deployment_checksum)
;

--rollback drop index orac_core.plg_dbdep_uk1_idx;
