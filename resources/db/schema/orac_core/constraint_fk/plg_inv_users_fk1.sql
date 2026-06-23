--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_fk_plg_inv_users_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_INV_USERS_FK1';
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: user foreign key for plugin_invocations


alter table orac_core.plugin_invocations
  add constraint plg_inv_users_fk1
  foreign key
  (
    user_id
  )
  references orac_core.users
  (
    user_id
  )
  on delete set null
;

--rollback alter table orac_core.plugin_invocations drop constraint plg_inv_users_fk1;
