--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_plg_inv_ck3 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_INV_CK3';
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: validates plugin_invocations execution status


alter table orac_core.plugin_invocations
  add constraint plg_inv_ck3
  check (
    execution_status in (
      'candidate_selected',
      'policy_evaluated',
      'confirmation_required',
      'confirmation_issued',
      'confirmation_accepted',
      'confirmation_rejected',
      'confirmation_expired',
      'confirmation_replay_rejected',
      'confirmation_mismatched',
      'execution_started',
      'completed',
      'failed',
      'timed_out',
      'denied'
    )
  )
;

--rollback alter table orac_core.plugin_invocations drop constraint plg_inv_ck3;
