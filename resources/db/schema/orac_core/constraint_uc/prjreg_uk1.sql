--liquibase formatted sql

--changeset clive:create_constraint_orac_core_prjreg_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PRJREG_UK1';
-- __author__: clive
-- __date__: 2026-07-11
-- __description__: unique project code constraint for project_registry

alter table orac_core.project_registry add constraint prjreg_uk1
  unique (project_code) using index orac_core.prjreg_uk1_idx;

--rollback alter table orac_core.project_registry drop constraint prjreg_uk1;
