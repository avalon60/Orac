--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_plg_inv_ck2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_INV_CK2';
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: validates plugin_invocations confirmation status


alter table orac_core.plugin_invocations
  add constraint plg_inv_ck2
  check (
    confirmation_status is null
    or confirmation_status in (
      'issued',
      'accepted',
      'rejected',
      'expired',
      'replayed',
      'replay_rejected',
      'mismatched',
      'missing',
      'pending'
    )
  )
;

--rollback alter table orac_core.plugin_invocations drop constraint plg_inv_ck2;
