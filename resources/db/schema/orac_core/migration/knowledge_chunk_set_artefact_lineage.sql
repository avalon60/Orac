--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Evolves chunk-set identity to include a normalised artefact source.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:add_orac_core_chunk_set_artefact_columns context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tab_cols where owner = 'ORAC_CORE' and table_name = 'KNOWLEDGE_CHUNK_SETS' and column_name = 'SOURCE_ARTEFACT_ID';
alter table orac_core.knowledge_chunk_sets add (
  source_artefact_id number,
  source_artefact_key number generated always as (nvl(source_artefact_id, -1)) virtual
);
--rollback alter table orac_core.knowledge_chunk_sets drop (source_artefact_key, source_artefact_id);

--changeset clive:replace_orac_core_kn_chset_uk1_for_artefacts context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:1 select count(1) from all_constraints where owner = 'ORAC_CORE' and table_name = 'KNOWLEDGE_CHUNK_SETS' and constraint_name = 'KN_CHSET_UK1';
alter table orac_core.knowledge_chunk_sets drop constraint kn_chset_uk1;
drop index orac_core.kn_chset_uk1_idx;
create unique index orac_core.kn_chset_uk1_idx
  on orac_core.knowledge_chunk_sets (
    extraction_id,
    source_artefact_key,
    chunker_code,
    chunker_version,
    chunk_size_tokens,
    overlap_tokens
  );
alter table orac_core.knowledge_chunk_sets add constraint kn_chset_uk1
  unique (
    extraction_id,
    source_artefact_key,
    chunker_code,
    chunker_version,
    chunk_size_tokens,
    overlap_tokens
  )
  using index orac_core.kn_chset_uk1_idx;
--rollback alter table orac_core.knowledge_chunk_sets drop constraint kn_chset_uk1; drop index orac_core.kn_chset_uk1_idx; create unique index orac_core.kn_chset_uk1_idx on orac_core.knowledge_chunk_sets (extraction_id, chunker_code, chunker_version, chunk_size_tokens, overlap_tokens); alter table orac_core.knowledge_chunk_sets add constraint kn_chset_uk1 unique (extraction_id, chunker_code, chunker_version, chunk_size_tokens, overlap_tokens) using index orac_core.kn_chset_uk1_idx;
