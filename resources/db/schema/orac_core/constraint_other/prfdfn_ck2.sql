--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_prfdfn_ck2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PRFDFN_CK2';
-- __author__: clive
-- __date__: 2026-04-27
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.preference_definitions
  add constraint prfdfn_ck2
  check
  (
    control_type in
    (
      'text',
      'textarea',
      'number',
      'checkbox',
      'select_list',
      'select_one',
      'popup_lov',
      'radio_group',
      'switch',
      'display_only'
    )
  )
;

--rollback alter table orac_core.preference_definitions drop constraint prfdfn_ck2;
