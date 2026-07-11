--liquibase formatted sql

--changeset clive:create_constraint_orac_core_prjreg_ck2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PRJREG_CK2';
-- __author__: clive
-- __date__: 2026-07-11
-- __description__: project code format validation for project_registry

alter table orac_core.project_registry add constraint prjreg_ck2
  check (regexp_like(project_code, '^[A-Z][A-Z0-9_]{1,99}$'));

--rollback alter table orac_core.project_registry drop constraint prjreg_ck2;
