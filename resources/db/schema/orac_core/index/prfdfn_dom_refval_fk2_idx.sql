--liquibase formatted sql

--changeset clive:create_index_orac_core_prfdfn_dom_refval_fk2_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'PRFDFN_DOM_REFVAL_FK2_IDX';
create index orac_core.prfdfn_dom_refval_fk2_idx
  on orac_core.preference_definitions
     (pref_control_type_domain_code, pref_control_type_ref_value_code);
--rollback drop index orac_core.prfdfn_dom_refval_fk2_idx;
