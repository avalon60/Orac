--liquibase formatted sql

--changeset clive:create_index_orac_core_index_plg_apxapp_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PLG_APXAPP_PK';
-- __author__: clive
-- __date__: 2026-06-20
-- __description__: primary key index for plugin_apex_apps

create unique index orac_core.plg_apxapp_pk
  on orac_core.plugin_apex_apps(plugin_apex_app_id);

--rollback drop index orac_core.plg_apxapp_pk;
