--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_pk_plg_apxapp_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_APXAPP_PK';
-- __author__: clive
-- __date__: 2026-06-20
-- __description__: primary key for plugin_apex_apps

alter table orac_core.plugin_apex_apps add constraint plg_apxapp_pk
  primary key (plugin_apex_app_id) using index orac_core.plg_apxapp_pk;

--rollback alter table orac_core.plugin_apex_apps drop constraint plg_apxapp_pk;
