--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_plg_inv_ck1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_INV_CK1';
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: validates plugin_invocations policy decision


alter table orac_core.plugin_invocations
  add constraint plg_inv_ck1
  check (
    policy_decision is null
    or policy_decision in ('allowed', 'denied', 'requires_confirmation')
  )
;

--rollback alter table orac_core.plugin_invocations drop constraint plg_inv_ck1;
