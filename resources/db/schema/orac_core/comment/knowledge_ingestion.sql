--liquibase formatted sql

--changeset clive:comment_orac_core_knowledge_ingestion context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.knowledge_source_objects is 'Stable external source identities accepted for Core knowledge ingestion.'
;
comment on table orac_core.knowledge_documents is 'Core knowledge document identities derived from accepted sources.'
;
comment on table orac_core.knowledge_document_versions is 'Content-addressed managed-file versions for knowledge documents.'
;
comment on table orac_core.knowledge_ingestion_requests is 'Durable Core ingestion queue and lifecycle state for managed-file processing.'
;
comment on table orac_core.knowledge_extractions is 'Extracted text payloads produced from managed document versions.'
;
comment on table orac_core.knowledge_chunk_sets is 'Chunking runs for a specific extraction and chunking strategy.'
;
comment on table orac_core.knowledge_chunks is 'Text chunks produced for retrieval and embedding.'
;
comment on table orac_core.knowledge_embedding_models is 'Embedding model identities used to create chunk vectors.'
;
comment on table orac_core.knowledge_chunk_embeddings is 'Chunk embedding vectors stored as JSON arrays for portable local retrieval.'
;
comment on table orac_core.knowledge_ingestion_events is 'Append-only Core ingestion lifecycle events.'
;
--rollback comment on table orac_core.knowledge_source_objects is null;
