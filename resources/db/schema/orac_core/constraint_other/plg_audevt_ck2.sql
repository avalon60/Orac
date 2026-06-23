--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_plg_audevt_ck2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_AUDEVT_CK2';
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: validates plugin_audit_events policy decision


alter table orac_core.plugin_audit_events
  add constraint plg_audevt_ck2
  check (
    policy_decision is null
    or policy_decision in ('allowed', 'denied', 'requires_confirmation')
  )
;

--rollback alter table orac_core.plugin_audit_events drop constraint plg_audevt_ck2;
