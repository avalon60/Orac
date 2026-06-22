--liquibase formatted sql

--changeset clive:create_constraint_orac_api_constraint_uc_prfdfn_v_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_API' and constraint_name = 'PRFDFN_V_UK1';
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: unique key metadata for the published preference definitions view

alter view orac_api.preference_definitions_v
  add constraint prfdfn_v_uk1
  unique (pref_key)
  rely disable novalidate
;
--rollback alter view orac_api.preference_definitions_v drop constraint prfdfn_v_uk1;
