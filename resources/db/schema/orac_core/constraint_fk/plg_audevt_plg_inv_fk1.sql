--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_fk_plg_audevt_plg_inv_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_AUDEVT_PLG_INV_FK1';
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: plugin invocation foreign key for plugin_audit_events


alter table orac_core.plugin_audit_events
  add constraint plg_audevt_plg_inv_fk1
  foreign key
  (
    plugin_invocation_id
  )
  references orac_core.plugin_invocations
  (
    plugin_invocation_id
  )
;

--rollback alter table orac_core.plugin_audit_events drop constraint plg_audevt_plg_inv_fk1;
