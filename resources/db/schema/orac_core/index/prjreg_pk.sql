--liquibase formatted sql

--changeset clive:create_index_orac_core_prjreg_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PRJREG_PK';
-- __author__: clive
-- __date__: 2026-07-11
-- __description__: primary-key index for project_registry

create unique index orac_core.prjreg_pk
  on orac_core.project_registry (project_id);

--rollback drop index orac_core.prjreg_pk;
