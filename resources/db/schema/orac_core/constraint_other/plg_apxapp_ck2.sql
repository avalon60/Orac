--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_plg_apxapp_ck2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_APXAPP_CK2';
-- __author__: clive
-- __date__: 2026-06-20
-- __description__: plugin_apex_apps install status validation

alter table orac_core.plugin_apex_apps add constraint plg_apxapp_ck2
  check (install_status in ('metadata_only', 'pending', 'installed', 'failed', 'skipped'));

--rollback alter table orac_core.plugin_apex_apps drop constraint plg_apxapp_ck2;
