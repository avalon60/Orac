--liquibase formatted sql

--changeset clive:create_index_orac_core_index_plg_apxapp_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PLG_APXAPP_UK1_IDX';
-- __author__: clive
-- __date__: 2026-06-20
-- __description__: unique plugin APEX app alias index

create unique index orac_core.plg_apxapp_uk1_idx
  on orac_core.plugin_apex_apps(plugin_id, app_alias);

--rollback drop index orac_core.plg_apxapp_uk1_idx;
