--liquibase formatted sql

--changeset clive:create_index_orac_core_prjreg_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PRJREG_UK1_IDX';
-- __author__: clive
-- __date__: 2026-07-11
-- __description__: unique project code index for project_registry

create unique index orac_core.prjreg_uk1_idx
  on orac_core.project_registry (project_code);

--rollback drop index orac_core.prjreg_uk1_idx;
