--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_uc_plgsvc_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLGSVC_UK1';
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: unique plugin service logical key

alter table orac_core.plugin_services
  add constraint plgsvc_uk1
  unique (plugin_id, service_code)
;

--rollback alter table orac_core.plugin_services drop constraint plgsvc_uk1;
