--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_pk_mesgs_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'MESGS_PK';
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.messages
  add constraint mesgs_pk
  primary key (message_id)
;

--rollback alter table orac_core.messages drop constraint mesgs_pk;
