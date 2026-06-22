--liquibase formatted sql

--changeset clive:create_constraint_orac_core_constraint_other_mesg_emb_ck1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'MESG_EMB_CK1';
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


alter table orac_core.message_embeddings
  add constraint mesg_emb_ck1
  check (distance_metric in ('COSINE', 'DOT', 'HAMMING', 'JACCARD', 'L2', 'L2_SQUARED', 'MANHATTAN'))
;

--rollback alter table orac_core.message_embeddings drop constraint mesg_emb_ck1;
