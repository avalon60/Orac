--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_plgsvc_ck3 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLGSVC_CK3';
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: validates plugin service code format

alter table orac_core.plugin_services add constraint plgsvc_ck3
  check (regexp_like(service_code, '^[a-z][a-z0-9_]{1,127}$'));

--rollback alter table orac_core.plugin_services drop constraint plgsvc_ck3;
