--liquibase formatted sql

--changeset clive:create_index_orac_core_user_pref_prfdfn_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'USER_PREF_PRFDFN_FK1_IDX';
create index orac_core.user_pref_prfdfn_fk1_idx
  on orac_core.user_preferences (pref_key);
--rollback drop index orac_core.user_pref_prfdfn_fk1_idx;
