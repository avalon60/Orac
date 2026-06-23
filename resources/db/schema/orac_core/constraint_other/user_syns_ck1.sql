--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_user_syns_ck1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'USER_SYNS_CK1';
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.user_synonyms
  add constraint user_syns_ck1
  check (is_active in ('N', 'Y'))
;

--rollback alter table orac_core.user_synonyms drop constraint user_syns_ck1;
