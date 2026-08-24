--liquibase formatted sql

--changeset clive:create_index_orac_core_mesg_emb_dom_refval_fk1_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'MESG_EMB_DOM_REFVAL_FK1_IDX';
create index orac_core.mesg_emb_dom_refval_fk1_idx
  on orac_core.message_embeddings
     (vector_distance_metric_domain_code, vector_distance_metric_ref_value_code);
--rollback drop index orac_core.mesg_emb_dom_refval_fk1_idx;
