--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_pk_plg_audevt_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PLG_AUDEVT_PK';
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: primary key for plugin_audit_events


alter table orac_core.plugin_audit_events
  add constraint plg_audevt_pk
  primary key (plugin_audit_event_id)
;

--rollback alter table orac_core.plugin_audit_events drop constraint plg_audevt_pk;
