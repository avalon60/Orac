--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_plgsvc_ck2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLGSVC_CK2';
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: validates plugin service lifecycle states

alter table orac_core.plugin_services add constraint plgsvc_ck2
  check (
    current_state in (
      'registered',
      'starting',
      'running',
      'stopping',
      'stopped',
      'failed',
      'disabled',
      'lease_lost'
    )
  );

--rollback alter table orac_core.plugin_services drop constraint plgsvc_ck2;
