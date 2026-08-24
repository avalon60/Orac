--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Creates immutable knowledge artefact uniqueness constraints.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_constraint_uc_orac_core_kn_artf_uk1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_ARTF_UK1';
alter table orac_core.knowledge_artefacts add constraint kn_artf_uk1
  unique (extraction_id, logical_name)
  using index orac_core.kn_artf_uk1_idx;
--rollback alter table orac_core.knowledge_artefacts drop constraint kn_artf_uk1;

--changeset clive:create_constraint_uc_orac_core_kn_artf_uk2 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_ARTF_UK2';
alter table orac_core.knowledge_artefacts add constraint kn_artf_uk2
  unique (extraction_id, member_ordinal)
  using index orac_core.kn_artf_uk2_idx;
--rollback alter table orac_core.knowledge_artefacts drop constraint kn_artf_uk2;

--changeset clive:create_constraint_uc_orac_core_kn_artf_uk3 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_ARTF_UK3';
alter table orac_core.knowledge_artefacts add constraint kn_artf_uk3
  unique (extraction_id, artefact_id)
  using index orac_core.kn_artf_uk3_idx;
--rollback alter table orac_core.knowledge_artefacts drop constraint kn_artf_uk3;
