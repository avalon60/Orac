--liquibase formatted sql

--changeset clive:create_constraint_orac_core_mesg_emb_ck1_distance_domain context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'MESG_EMB_CK1';
alter table orac_core.message_embeddings add constraint mesg_emb_ck1
  check (vector_distance_metric_domain_code = 'VECTOR_DISTANCE_METRIC');
--rollback alter table orac_core.message_embeddings drop constraint mesg_emb_ck1;
