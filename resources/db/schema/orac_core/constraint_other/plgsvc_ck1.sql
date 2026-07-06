--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_plgsvc_ck1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLGSVC_CK1';
-- __author__: clive
-- __date__: 2026-07-02
-- __description__: validates plugin service policy values

alter table orac_core.plugin_services add constraint plgsvc_ck1
  check (
    manifest_policy in ('disabled', 'manual', 'auto')
    and (policy_override is null or policy_override in ('disabled', 'manual', 'auto'))
  );

--rollback alter table orac_core.plugin_services drop constraint plgsvc_ck1;
