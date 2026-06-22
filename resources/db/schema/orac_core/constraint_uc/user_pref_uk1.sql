--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_uc_user_pref_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'USER_PREF_UK1';
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.user_preferences
  add constraint user_pref_uk1
  unique (user_id, pref_key)
;

--rollback alter table orac_core.user_preferences drop constraint user_pref_uk1;
