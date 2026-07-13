--liquibase formatted sql

--changeset clive:create_constraint_uc_orac_core_kn_srcobj_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_SRCOBJ_UK1';
alter table orac_core.knowledge_source_objects add constraint kn_srcobj_uk1
  unique (source_type, source_reference)
  using index orac_core.kn_srcobj_uk1_idx;
--rollback alter table orac_core.knowledge_source_objects drop constraint kn_srcobj_uk1;

--changeset clive:create_constraint_uc_orac_core_kn_doc_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_DOC_UK1';
alter table orac_core.knowledge_documents add constraint kn_doc_uk1
  unique (source_object_id)
  using index orac_core.kn_doc_uk1_idx;
--rollback alter table orac_core.knowledge_documents drop constraint kn_doc_uk1;

--changeset clive:create_constraint_uc_orac_core_kn_docver_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_DOCVER_UK1';
alter table orac_core.knowledge_document_versions add constraint kn_docver_uk1
  unique (document_id, content_sha256)
  using index orac_core.kn_docver_uk1_idx;
--rollback alter table orac_core.knowledge_document_versions drop constraint kn_docver_uk1;

--changeset clive:create_constraint_uc_orac_core_kn_ingreq_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_INGREQ_UK1';
alter table orac_core.knowledge_ingestion_requests add constraint kn_ingreq_uk1
  unique (source_object_id, document_version_id)
  using index orac_core.kn_ingreq_uk1_idx;
--rollback alter table orac_core.knowledge_ingestion_requests drop constraint kn_ingreq_uk1;

--changeset clive:create_constraint_uc_orac_core_kn_ext_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EXT_UK1';
alter table orac_core.knowledge_extractions add constraint kn_ext_uk1
  unique (
    document_version_id,
    extractor_code,
    extractor_version,
    text_sha256
  )
  using index orac_core.kn_ext_uk1_idx;
--rollback alter table orac_core.knowledge_extractions drop constraint kn_ext_uk1;

--changeset clive:create_constraint_uc_orac_core_kn_chset_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHSET_UK1';
alter table orac_core.knowledge_chunk_sets add constraint kn_chset_uk1
  unique (
    extraction_id,
    chunker_code,
    chunker_version,
    chunk_size_tokens,
    overlap_tokens
  )
  using index orac_core.kn_chset_uk1_idx;
--rollback alter table orac_core.knowledge_chunk_sets drop constraint kn_chset_uk1;

--changeset clive:create_constraint_uc_orac_core_kn_chnk_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNK_UK1';
alter table orac_core.knowledge_chunks add constraint kn_chnk_uk1
  unique (chunk_set_id, chunk_no)
  using index orac_core.kn_chnk_uk1_idx;
--rollback alter table orac_core.knowledge_chunks drop constraint kn_chnk_uk1;

--changeset clive:create_constraint_uc_orac_core_kn_embmod_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EMBMOD_UK1';
alter table orac_core.knowledge_embedding_models add constraint kn_embmod_uk1
  unique (
    provider_code,
    model_name,
    model_revision,
    dimensions,
    distance_metric,
    normalisation
  )
  using index orac_core.kn_embmod_uk1_idx;
--rollback alter table orac_core.knowledge_embedding_models drop constraint kn_embmod_uk1;

--changeset clive:create_constraint_uc_orac_core_kn_chnkemb_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNKEMB_UK1';
alter table orac_core.knowledge_chunk_embeddings add constraint kn_chnkemb_uk1
  unique (
    chunk_id,
    embedding_model_id,
    embedding_text_sha256
  )
  using index orac_core.kn_chnkemb_uk1_idx;
--rollback alter table orac_core.knowledge_chunk_embeddings drop constraint kn_chnkemb_uk1;
