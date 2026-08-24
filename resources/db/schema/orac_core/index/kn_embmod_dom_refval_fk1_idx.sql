--liquibase formatted sql

--changeset clive:create_index_orac_core_kn_embmod_dom_refval_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_EMBMOD_DOM_REFVAL_FK1_IDX';
create index orac_core.kn_embmod_dom_refval_fk1_idx
  on orac_core.knowledge_embedding_models
     (vector_distance_metric_domain_code, vector_distance_metric_ref_value_code);
--rollback drop index orac_core.kn_embmod_dom_refval_fk1_idx;
