--liquibase formatted sql

--changeset clive:create_constraint_orac_core_kn_embmod_dom_refval_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EMBMOD_DOM_REFVAL_FK1';
alter table orac_core.knowledge_embedding_models add constraint kn_embmod_dom_refval_fk1
  foreign key (vector_distance_metric_domain_code, vector_distance_metric_ref_value_code)
  references orac_core.domain_ref_values (domain_code, ref_value_code);
--rollback alter table orac_core.knowledge_embedding_models drop constraint kn_embmod_dom_refval_fk1;
