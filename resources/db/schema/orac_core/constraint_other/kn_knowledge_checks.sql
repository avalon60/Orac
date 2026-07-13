--liquibase formatted sql

--changeset clive:create_constraint_other_orac_core_kn_srcobj_scope_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_SRCOBJ_SCOPE_CK';
alter table orac_core.knowledge_source_objects add constraint kn_srcobj_scope_ck
  check (target_scope_type in ('PROJECT', 'PLUGIN'));
--rollback alter table orac_core.knowledge_source_objects drop constraint kn_srcobj_scope_ck;

--changeset clive:create_constraint_other_orac_core_kn_doc_scope_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_DOC_SCOPE_CK';
alter table orac_core.knowledge_documents add constraint kn_doc_scope_ck
  check (target_scope_type in ('PROJECT', 'PLUGIN'));
--rollback alter table orac_core.knowledge_documents drop constraint kn_doc_scope_ck;

--changeset clive:create_constraint_other_orac_core_kn_docver_hash_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_DOCVER_HASH_CK';
alter table orac_core.knowledge_document_versions add constraint kn_docver_hash_ck
  check (regexp_like(content_sha256, '^[0-9a-f]{64}$'));
--rollback alter table orac_core.knowledge_document_versions drop constraint kn_docver_hash_ck;

--changeset clive:create_constraint_other_orac_core_kn_docver_size_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_DOCVER_SIZE_CK';
alter table orac_core.knowledge_document_versions add constraint kn_docver_size_ck
  check (byte_size >= 0);
--rollback alter table orac_core.knowledge_document_versions drop constraint kn_docver_size_ck;

--changeset clive:create_constraint_other_orac_core_kn_ingreq_status_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_INGREQ_STATUS_CK';
alter table orac_core.knowledge_ingestion_requests add constraint kn_ingreq_status_ck
  check (status_code in ('QUEUED', 'PROCESSING', 'RETRY_WAIT', 'COMPLETED', 'FAILED'));
--rollback alter table orac_core.knowledge_ingestion_requests drop constraint kn_ingreq_status_ck;

--changeset clive:create_constraint_other_orac_core_kn_ingreq_stage_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_INGREQ_STAGE_CK';
alter table orac_core.knowledge_ingestion_requests add constraint kn_ingreq_stage_ck
  check (stage_code in ('SUBMITTED', 'CLAIMED', 'EXTRACT', 'CHUNK', 'EMBED', 'COMPLETED', 'FAILED', 'RETRY_WAIT'));
--rollback alter table orac_core.knowledge_ingestion_requests drop constraint kn_ingreq_stage_ck;

--changeset clive:create_constraint_other_orac_core_kn_ingreq_attempt_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_INGREQ_ATTEMPT_CK';
alter table orac_core.knowledge_ingestion_requests add constraint kn_ingreq_attempt_ck
  check (attempts >= 0 and max_attempts > 0);
--rollback alter table orac_core.knowledge_ingestion_requests drop constraint kn_ingreq_attempt_ck;

--changeset clive:create_constraint_other_orac_core_kn_ext_hash_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EXT_HASH_CK';
alter table orac_core.knowledge_extractions add constraint kn_ext_hash_ck
  check (regexp_like(text_sha256, '^[0-9a-f]{64}$'));
--rollback alter table orac_core.knowledge_extractions drop constraint kn_ext_hash_ck;

--changeset clive:create_constraint_other_orac_core_kn_chset_size_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHSET_SIZE_CK';
alter table orac_core.knowledge_chunk_sets add constraint kn_chset_size_ck
  check (chunk_size_tokens > 0 and overlap_tokens >= 0 and overlap_tokens < chunk_size_tokens);
--rollback alter table orac_core.knowledge_chunk_sets drop constraint kn_chset_size_ck;

--changeset clive:create_constraint_other_orac_core_kn_chnk_span_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNK_SPAN_CK';
alter table orac_core.knowledge_chunks add constraint kn_chnk_span_ck
  check (chunk_no > 0 and span_start >= 0 and span_end >= span_start and token_count >= 0);
--rollback alter table orac_core.knowledge_chunks drop constraint kn_chnk_span_ck;

--changeset clive:create_constraint_other_orac_core_kn_chnk_hash_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNK_HASH_CK';
alter table orac_core.knowledge_chunks add constraint kn_chnk_hash_ck
  check (regexp_like(content_sha256, '^[0-9a-f]{64}$'));
--rollback alter table orac_core.knowledge_chunks drop constraint kn_chnk_hash_ck;

--changeset clive:create_constraint_other_orac_core_kn_embmod_shape_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_EMBMOD_SHAPE_CK';
alter table orac_core.knowledge_embedding_models add constraint kn_embmod_shape_ck
  check (dimensions > 0 and active_yn in ('Y', 'N'));
--rollback alter table orac_core.knowledge_embedding_models drop constraint kn_embmod_shape_ck;

--changeset clive:create_constraint_other_orac_core_kn_chnkemb_hash_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNKEMB_HASH_CK';
alter table orac_core.knowledge_chunk_embeddings add constraint kn_chnkemb_hash_ck
  check (regexp_like(embedding_text_sha256, '^[0-9a-f]{64}$'));
--rollback alter table orac_core.knowledge_chunk_embeddings drop constraint kn_chnkemb_hash_ck;

--changeset clive:create_constraint_other_orac_core_kn_chnkemb_json_ck context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHNKEMB_JSON_CK';
alter table orac_core.knowledge_chunk_embeddings add constraint kn_chnkemb_json_ck
  check (embedding_vector is json);
--rollback alter table orac_core.knowledge_chunk_embeddings drop constraint kn_chnkemb_json_ck;
