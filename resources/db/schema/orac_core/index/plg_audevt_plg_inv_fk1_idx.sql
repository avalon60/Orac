--liquibase formatted sql

--changeset clive:create_index_orac_core_index_plg_audevt_plg_inv_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PLG_AUDEVT_PLG_INV_FK1_IDX';
-- __author__: clive
-- __date__: 2026-05-25
-- __description__: plugin invocation foreign key index for plugin_audit_events


create index orac_core.plg_audevt_plg_inv_fk1_idx
  on orac_core.plugin_audit_events
  (
    plugin_invocation_id asc
  )
;

--rollback drop index orac_core.plg_audevt_plg_inv_fk1_idx;
