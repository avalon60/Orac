--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_pk_user_syns_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'USER_SYNS_PK';
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.user_synonyms
  add constraint user_syns_pk
  primary key (alias_type, alias_value)
;

--rollback alter table orac_core.user_synonyms drop constraint user_syns_pk;
