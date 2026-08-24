--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Creates the knowledge artefact primary key.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_constraint_pk_orac_core_kn_artf_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_ARTF_PK';
alter table orac_core.knowledge_artefacts add constraint kn_artf_pk
  primary key (artefact_id)
  using index orac_core.kn_artf_pk;
--rollback alter table orac_core.knowledge_artefacts drop constraint kn_artf_pk;
