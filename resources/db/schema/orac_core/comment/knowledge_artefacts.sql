--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Documents immutable normalised knowledge artefact lineage.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:comment_orac_core_knowledge_artefacts context:core labels:core stripComments:false runOnChange:true
comment on table orac_core.knowledge_artefacts is 'Immutable normalised output members produced by one knowledge extraction and stored in the Core managed content store.';
comment on column orac_core.knowledge_artefacts.artefact_id is 'Surrogate identity of the normalised artefact lineage row.';
comment on column orac_core.knowledge_artefacts.extraction_id is 'Extractor run that owns the complete output set.';
comment on column orac_core.knowledge_artefacts.artefact_role_code is 'Member role: PRIMARY, MANIFEST, TABLE, or METADATA.';
comment on column orac_core.knowledge_artefacts.storage_key is 'Logical sha256 content-store key; never a caller-supplied filesystem path.';
comment on column orac_core.knowledge_artefacts.metadata_json is 'Bounded versioned member provenance; labels remain untrusted data.';
--rollback comment on table orac_core.knowledge_artefacts is null;
