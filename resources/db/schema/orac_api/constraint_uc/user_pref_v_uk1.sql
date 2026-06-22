--liquibase formatted sql

--changeset clive:create_constraint_orac_api_constraint_uc_user_pref_v_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_API' and constraint_name = 'USER_PREF_V_UK1';
-- __author__: clive
-- __date__: 2026-04-25
-- __description__: unique key metadata for the published preferences view

alter view orac_api.user_preferences_v
  add constraint user_pref_v_uk1
  unique (user_id, pref_key)
  rely disable novalidate
;
--rollback alter view orac_api.user_preferences_v drop constraint user_pref_v_uk1;
