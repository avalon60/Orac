--liquibase formatted sql

--changeset clive:create_constraint_fk_orac_core_kn_doc_kn_srcobj_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_DOC_KN_SRCOBJ_FK1';
alter table orac_core.knowledge_documents add constraint kn_doc_kn_srcobj_fk1
  foreign key (source_object_id)
  references orac_core.knowledge_source_objects (source_object_id);
--rollback alter table orac_core.knowledge_documents drop constraint kn_doc_kn_srcobj_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_doc_kn_docver_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_DOC_KN_DOCVER_FK1';
alter table orac_core.knowledge_documents add constraint kn_doc_kn_docver_fk1
  foreign key (current_document_version_id)
  references orac_core.knowledge_document_versions (document_version_id)
  deferrable initially deferred;
--rollback alter table orac_core.knowledge_documents drop constraint kn_doc_kn_docver_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_docver_kn_doc_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_DOCVER_KN_DOC_FK1';
alter table orac_core.knowledge_document_versions add constraint kn_docver_kn_doc_fk1
  foreign key (document_id)
  references orac_core.knowledge_documents (document_id);
--rollback alter table orac_core.knowledge_document_versions drop constraint kn_docver_kn_doc_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_docver_kn_srcobj_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_DOCVER_KN_SRCOBJ_FK1';
alter table orac_core.knowledge_document_versions add constraint kn_docver_kn_srcobj_fk1
  foreign key (source_object_id)
  references orac_core.knowledge_source_objects (source_object_id);
--rollback alter table orac_core.knowledge_document_versions drop constraint kn_docver_kn_srcobj_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_ingreq_kn_srcobj_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_INGREQ_KN_SRCOBJ_FK1';
alter table orac_core.knowledge_ingestion_requests add constraint kn_ingreq_kn_srcobj_fk1
  foreign key (source_object_id)
  references orac_core.knowledge_source_objects (source_object_id);
--rollback alter table orac_core.knowledge_ingestion_requests drop constraint kn_ingreq_kn_srcobj_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_ingreq_kn_doc_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_INGREQ_KN_DOC_FK1';
alter table orac_core.knowledge_ingestion_requests add constraint kn_ingreq_kn_doc_fk1
  foreign key (document_id)
  references orac_core.knowledge_documents (document_id);
--rollback alter table orac_core.knowledge_ingestion_requests drop constraint kn_ingreq_kn_doc_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_ingreq_kn_docver_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_INGREQ_KN_DOCVER_FK1';
alter table orac_core.knowledge_ingestion_requests add constraint kn_ingreq_kn_docver_fk1
  foreign key (document_version_id)
  references orac_core.knowledge_document_versions (document_version_id);
--rollback alter table orac_core.knowledge_ingestion_requests drop constraint kn_ingreq_kn_docver_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_ext_kn_docver_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EXT_KN_DOCVER_FK1';
alter table orac_core.knowledge_extractions add constraint kn_ext_kn_docver_fk1
  foreign key (document_version_id)
  references orac_core.knowledge_document_versions (document_version_id);
--rollback alter table orac_core.knowledge_extractions drop constraint kn_ext_kn_docver_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_chset_kn_ext_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHSET_KN_EXT_FK1';
alter table orac_core.knowledge_chunk_sets add constraint kn_chset_kn_ext_fk1
  foreign key (extraction_id)
  references orac_core.knowledge_extractions (extraction_id);
--rollback alter table orac_core.knowledge_chunk_sets drop constraint kn_chset_kn_ext_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_chnk_kn_chset_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNK_KN_CHSET_FK1';
alter table orac_core.knowledge_chunks add constraint kn_chnk_kn_chset_fk1
  foreign key (chunk_set_id)
  references orac_core.knowledge_chunk_sets (chunk_set_id);
--rollback alter table orac_core.knowledge_chunks drop constraint kn_chnk_kn_chset_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_chnkemb_kn_chnk_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNKEMB_KN_CHNK_FK1';
alter table orac_core.knowledge_chunk_embeddings add constraint kn_chnkemb_kn_chnk_fk1
  foreign key (chunk_id)
  references orac_core.knowledge_chunks (chunk_id);
--rollback alter table orac_core.knowledge_chunk_embeddings drop constraint kn_chnkemb_kn_chnk_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_chnkemb_kn_embmod_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNKEMB_KN_EMBMOD_FK1';
alter table orac_core.knowledge_chunk_embeddings add constraint kn_chnkemb_kn_embmod_fk1
  foreign key (embedding_model_id)
  references orac_core.knowledge_embedding_models (embedding_model_id);
--rollback alter table orac_core.knowledge_chunk_embeddings drop constraint kn_chnkemb_kn_embmod_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_inge_kn_ingreq_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_INGE_KN_INGREQ_FK1';
alter table orac_core.knowledge_ingestion_events add constraint kn_inge_kn_ingreq_fk1
  foreign key (ingestion_request_id)
  references orac_core.knowledge_ingestion_requests (ingestion_request_id);
--rollback alter table orac_core.knowledge_ingestion_events drop constraint kn_inge_kn_ingreq_fk1;
