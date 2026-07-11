--liquibase formatted sql

--changeset clive:create_constraint_orac_core_prjreg_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PRJREG_PK';
-- __author__: clive
-- __date__: 2026-07-11
-- __description__: primary key for project_registry

alter table orac_core.project_registry add constraint prjreg_pk
  primary key (project_id) using index orac_core.prjreg_pk;

--rollback alter table orac_core.project_registry drop constraint prjreg_pk;
