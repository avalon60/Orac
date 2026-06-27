--liquibase formatted sql
-- Author: clive
-- Date: 26-Jun-2026
-- Description: Validates slider preference metadata shape.

--changeset clive:create_constraint_orac_core_constraint_other_prfdfn_ck7 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'PRFDFN_CK7';
alter table orac_core.preference_definitions
  add constraint prfdfn_ck7
  check
  (
    control_type <> 'slider'
    or
    (
      value_type = 'number'
      and min_number is not null
      and max_number is not null
      and step_number is not null
      and step_number > 0
      and min_number <= max_number
    )
  )
;

--rollback alter table orac_core.preference_definitions drop constraint prfdfn_ck7;
