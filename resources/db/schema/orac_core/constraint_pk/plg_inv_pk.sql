--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_pk_plg_inv_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_INV_PK';
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: primary key for plugin_invocations


alter table orac_core.plugin_invocations
  add constraint plg_inv_pk
  primary key (plugin_invocation_id)
;

--rollback alter table orac_core.plugin_invocations drop constraint plg_inv_pk;
