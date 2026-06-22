--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_uc_plgreg_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLGREG_UK1';
-- __author__: clive
-- __date__: 2026-06-07
-- __description__: one current registry row per plugin

alter table orac_core.plugin_registry add constraint plgreg_uk1
  unique (plugin_id) using index orac_core.plgreg_uk1_idx;

--rollback alter table orac_core.plugin_registry drop constraint plgreg_uk1;
