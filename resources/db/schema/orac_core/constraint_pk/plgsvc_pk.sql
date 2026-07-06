--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_pk_plgsvc_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLGSVC_PK';
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: primary key for plugin_services

alter table orac_core.plugin_services
  add constraint plgsvc_pk
  primary key (plugin_service_id)
;

--rollback alter table orac_core.plugin_services drop constraint plgsvc_pk;
