--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Creates knowledge artefact lineage foreign keys.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_constraint_fk_orac_core_kn_artf_kn_ext_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_ARTF_KN_EXT_FK1';
alter table orac_core.knowledge_artefacts add constraint kn_artf_kn_ext_fk1
  foreign key (extraction_id)
  references orac_core.knowledge_extractions (extraction_id);
--rollback alter table orac_core.knowledge_artefacts drop constraint kn_artf_kn_ext_fk1;

--changeset clive:create_constraint_fk_orac_core_kn_chset_kn_artf_fk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_CHSET_KN_ARTF_FK1';
alter table orac_core.knowledge_chunk_sets add constraint kn_chset_kn_artf_fk1
  foreign key (extraction_id, source_artefact_id)
  references orac_core.knowledge_artefacts (extraction_id, artefact_id);
--rollback alter table orac_core.knowledge_chunk_sets drop constraint kn_chset_kn_artf_fk1;
