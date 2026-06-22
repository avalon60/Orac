--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_pk_plgreg_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLGREG_PK';
-- __author__: clive
-- __date__: 2026-06-07
-- __description__: primary key for plugin_registry

alter table orac_core.plugin_registry add constraint plgreg_pk
  primary key (plugin_registry_id) using index orac_core.plgreg_pk;

--rollback alter table orac_core.plugin_registry drop constraint plgreg_pk;
