--liquibase formatted sql

--changeset clive:create_constraint_orac_core_kn_embmod_ck2_distance_domain context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EMBMOD_CK2';
alter table orac_core.knowledge_embedding_models add constraint kn_embmod_ck2
  check (vector_distance_metric_domain_code = 'VECTOR_DISTANCE_METRIC');
--rollback alter table orac_core.knowledge_embedding_models drop constraint kn_embmod_ck2;
