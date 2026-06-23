--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_uc_plg_apxapp_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_APXAPP_UK1';
-- __author__: clive
-- __date__: 2026-06-20
-- __description__: one current APEX app registry row per plugin alias

alter table orac_core.plugin_apex_apps add constraint plg_apxapp_uk1
  unique (plugin_id, app_alias) using index orac_core.plg_apxapp_uk1_idx;

--rollback alter table orac_core.plugin_apex_apps drop constraint plg_apxapp_uk1;
