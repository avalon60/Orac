--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_plg_apxapp_ck1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_APXAPP_CK1';
-- __author__: clive
-- __date__: 2026-06-20
-- __description__: plugin_apex_apps enabled flag validation

alter table orac_core.plugin_apex_apps add constraint plg_apxapp_ck1
  check (enabled in ('Y', 'N'));

--rollback alter table orac_core.plugin_apex_apps drop constraint plg_apxapp_ck1;
