--liquibase formatted sql
-- Author: clive
-- Date: 26-Jun-2026
-- Description: Extends preference control type validation to allow slider controls.

--changeset clive:drop_old_prfdfn_ck2_for_slider_control_type context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_constraints where owner = 'ORAC_CORE' and table_name = 'PREFERENCE_DEFINITIONS' and constraint_name = 'PRFDFN_CK2' and search_condition_vc not like '%''slider''%';
alter table orac_core.preference_definitions
  drop constraint prfdfn_ck2
;

--rollback alter table orac_core.preference_definitions add constraint prfdfn_ck2 check (control_type in ('text', 'textarea', 'number', 'checkbox', 'select_list', 'select_one', 'popup_lov', 'radio_group', 'switch', 'display_only'));

--changeset clive:add_prfdfn_ck2_with_slider_control_type context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and table_name = 'PREFERENCE_DEFINITIONS' and constraint_name = 'PRFDFN_CK2';
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
      'slider',
      'display_only'
    )
  )
;

--rollback alter table orac_core.preference_definitions drop constraint prfdfn_ck2;
