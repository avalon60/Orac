--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_fk_mesg_emb_mesgs_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'MESG_EMB_MESGS_FK1';
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.message_embeddings
  add constraint mesg_emb_mesgs_fk1
  foreign key
  (
    message_id
  )
  references orac_core.messages
  (
    message_id
  )
  on delete cascade
;

--rollback alter table orac_core.message_embeddings drop constraint mesg_emb_mesgs_fk1;
