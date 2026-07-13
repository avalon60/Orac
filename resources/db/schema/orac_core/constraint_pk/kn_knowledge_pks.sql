--liquibase formatted sql

--changeset clive:create_constraint_pk_orac_core_kn_srcobj_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_SRCOBJ_PK';
alter table orac_core.knowledge_source_objects add constraint kn_srcobj_pk
  primary key (source_object_id)
  using index orac_core.kn_srcobj_pk;
--rollback alter table orac_core.knowledge_source_objects drop constraint kn_srcobj_pk;

--changeset clive:create_constraint_pk_orac_core_kn_doc_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_DOC_PK';
alter table orac_core.knowledge_documents add constraint kn_doc_pk
  primary key (document_id)
  using index orac_core.kn_doc_pk;
--rollback alter table orac_core.knowledge_documents drop constraint kn_doc_pk;

--changeset clive:create_constraint_pk_orac_core_kn_docver_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_DOCVER_PK';
alter table orac_core.knowledge_document_versions add constraint kn_docver_pk
  primary key (document_version_id)
  using index orac_core.kn_docver_pk;
--rollback alter table orac_core.knowledge_document_versions drop constraint kn_docver_pk;

--changeset clive:create_constraint_pk_orac_core_kn_ingreq_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_INGREQ_PK';
alter table orac_core.knowledge_ingestion_requests add constraint kn_ingreq_pk
  primary key (ingestion_request_id)
  using index orac_core.kn_ingreq_pk;
--rollback alter table orac_core.knowledge_ingestion_requests drop constraint kn_ingreq_pk;

--changeset clive:create_constraint_pk_orac_core_kn_ext_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EXT_PK';
alter table orac_core.knowledge_extractions add constraint kn_ext_pk
  primary key (extraction_id)
  using index orac_core.kn_ext_pk;
--rollback alter table orac_core.knowledge_extractions drop constraint kn_ext_pk;

--changeset clive:create_constraint_pk_orac_core_kn_chset_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHSET_PK';
alter table orac_core.knowledge_chunk_sets add constraint kn_chset_pk
  primary key (chunk_set_id)
  using index orac_core.kn_chset_pk;
--rollback alter table orac_core.knowledge_chunk_sets drop constraint kn_chset_pk;

--changeset clive:create_constraint_pk_orac_core_kn_chnk_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNK_PK';
alter table orac_core.knowledge_chunks add constraint kn_chnk_pk
  primary key (chunk_id)
  using index orac_core.kn_chnk_pk;
--rollback alter table orac_core.knowledge_chunks drop constraint kn_chnk_pk;

--changeset clive:create_constraint_pk_orac_core_kn_embmod_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EMBMOD_PK';
alter table orac_core.knowledge_embedding_models add constraint kn_embmod_pk
  primary key (embedding_model_id)
  using index orac_core.kn_embmod_pk;
--rollback alter table orac_core.knowledge_embedding_models drop constraint kn_embmod_pk;

--changeset clive:create_constraint_pk_orac_core_kn_chnkemb_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNKEMB_PK';
alter table orac_core.knowledge_chunk_embeddings add constraint kn_chnkemb_pk
  primary key (chunk_embedding_id)
  using index orac_core.kn_chnkemb_pk;
--rollback alter table orac_core.knowledge_chunk_embeddings drop constraint kn_chnkemb_pk;

--changeset clive:create_constraint_pk_orac_core_kn_inge_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_INGE_PK';
alter table orac_core.knowledge_ingestion_events add constraint kn_inge_pk
  primary key (ingestion_event_id)
  using index orac_core.kn_inge_pk;
--rollback alter table orac_core.knowledge_ingestion_events drop constraint kn_inge_pk;
