--liquibase formatted sql

--changeset clive:create_index_orac_core_kn_srcobj_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_SRCOBJ_PK';
create unique index orac_core.kn_srcobj_pk
  on orac_core.knowledge_source_objects (source_object_id);
--rollback drop index orac_core.kn_srcobj_pk;

--changeset clive:create_index_orac_core_kn_srcobj_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_SRCOBJ_UK1_IDX';
create unique index orac_core.kn_srcobj_uk1_idx
  on orac_core.knowledge_source_objects (source_type, source_reference);
--rollback drop index orac_core.kn_srcobj_uk1_idx;

--changeset clive:create_index_orac_core_kn_doc_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_DOC_PK';
create unique index orac_core.kn_doc_pk
  on orac_core.knowledge_documents (document_id);
--rollback drop index orac_core.kn_doc_pk;

--changeset clive:create_index_orac_core_kn_doc_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_DOC_UK1_IDX';
create unique index orac_core.kn_doc_uk1_idx
  on orac_core.knowledge_documents (source_object_id);
--rollback drop index orac_core.kn_doc_uk1_idx;

--changeset clive:create_index_orac_core_kn_docver_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_DOCVER_PK';
create unique index orac_core.kn_docver_pk
  on orac_core.knowledge_document_versions (document_version_id);
--rollback drop index orac_core.kn_docver_pk;

--changeset clive:create_index_orac_core_kn_docver_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_DOCVER_UK1_IDX';
create unique index orac_core.kn_docver_uk1_idx
  on orac_core.knowledge_document_versions (document_id, content_sha256);
--rollback drop index orac_core.kn_docver_uk1_idx;

--changeset clive:create_index_orac_core_kn_ingreq_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_INGREQ_PK';
create unique index orac_core.kn_ingreq_pk
  on orac_core.knowledge_ingestion_requests (ingestion_request_id);
--rollback drop index orac_core.kn_ingreq_pk;

--changeset clive:create_index_orac_core_kn_ingreq_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_INGREQ_UK1_IDX';
create unique index orac_core.kn_ingreq_uk1_idx
  on orac_core.knowledge_ingestion_requests (source_object_id, document_version_id);
--rollback drop index orac_core.kn_ingreq_uk1_idx;

--changeset clive:create_index_orac_core_kn_ingreq_status_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_INGREQ_STATUS_IDX';
create index orac_core.kn_ingreq_status_idx
  on orac_core.knowledge_ingestion_requests (status_code, next_attempt_on, lease_expires_on);
--rollback drop index orac_core.kn_ingreq_status_idx;

--changeset clive:create_index_orac_core_kn_ext_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_EXT_PK';
create unique index orac_core.kn_ext_pk
  on orac_core.knowledge_extractions (extraction_id);
--rollback drop index orac_core.kn_ext_pk;

--changeset clive:create_index_orac_core_kn_ext_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_EXT_UK1_IDX';
create unique index orac_core.kn_ext_uk1_idx
  on orac_core.knowledge_extractions (
    document_version_id,
    extractor_code,
    extractor_version,
    text_sha256
  );
--rollback drop index orac_core.kn_ext_uk1_idx;

--changeset clive:create_index_orac_core_kn_chset_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_CHSET_PK';
create unique index orac_core.kn_chset_pk
  on orac_core.knowledge_chunk_sets (chunk_set_id);
--rollback drop index orac_core.kn_chset_pk;

--changeset clive:create_index_orac_core_kn_chset_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_CHSET_UK1_IDX';
create unique index orac_core.kn_chset_uk1_idx
  on orac_core.knowledge_chunk_sets (
    extraction_id,
    chunker_code,
    chunker_version,
    chunk_size_tokens,
    overlap_tokens
  );
--rollback drop index orac_core.kn_chset_uk1_idx;

--changeset clive:create_index_orac_core_kn_chnk_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_CHNK_PK';
create unique index orac_core.kn_chnk_pk
  on orac_core.knowledge_chunks (chunk_id);
--rollback drop index orac_core.kn_chnk_pk;

--changeset clive:create_index_orac_core_kn_chnk_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_CHNK_UK1_IDX';
create unique index orac_core.kn_chnk_uk1_idx
  on orac_core.knowledge_chunks (chunk_set_id, chunk_no);
--rollback drop index orac_core.kn_chnk_uk1_idx;

--changeset clive:create_index_orac_core_kn_embmod_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_EMBMOD_PK';
create unique index orac_core.kn_embmod_pk
  on orac_core.knowledge_embedding_models (embedding_model_id);
--rollback drop index orac_core.kn_embmod_pk;

--changeset clive:create_index_orac_core_kn_embmod_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_EMBMOD_UK1_IDX';
create unique index orac_core.kn_embmod_uk1_idx
  on orac_core.knowledge_embedding_models (
    provider_code,
    model_name,
    model_revision,
    dimensions,
    distance_metric,
    normalisation
  );
--rollback drop index orac_core.kn_embmod_uk1_idx;

--changeset clive:create_index_orac_core_kn_chnkemb_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_CHNKEMB_PK';
create unique index orac_core.kn_chnkemb_pk
  on orac_core.knowledge_chunk_embeddings (chunk_embedding_id);
--rollback drop index orac_core.kn_chnkemb_pk;

--changeset clive:create_index_orac_core_kn_chnkemb_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_CHNKEMB_UK1_IDX';
create unique index orac_core.kn_chnkemb_uk1_idx
  on orac_core.knowledge_chunk_embeddings (
    chunk_id,
    embedding_model_id,
    embedding_text_sha256
  );
--rollback drop index orac_core.kn_chnkemb_uk1_idx;

--changeset clive:create_index_orac_core_kn_inge_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_INGE_PK';
create unique index orac_core.kn_inge_pk
  on orac_core.knowledge_ingestion_events (ingestion_event_id);
--rollback drop index orac_core.kn_inge_pk;

--changeset clive:create_index_orac_core_kn_inge_req_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_INGE_REQ_IDX';
create index orac_core.kn_inge_req_idx
  on orac_core.knowledge_ingestion_events (ingestion_request_id, event_ts);
--rollback drop index orac_core.kn_inge_req_idx;
