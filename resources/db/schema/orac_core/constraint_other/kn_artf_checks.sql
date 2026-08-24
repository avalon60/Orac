--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Enforces immutable knowledge artefact descriptor shapes.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_constraint_other_orac_core_kn_artf_id_ck context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_ARTF_ID_CK';
alter table orac_core.knowledge_artefacts add constraint kn_artf_id_ck
  check (artefact_id > 0);
--rollback alter table orac_core.knowledge_artefacts drop constraint kn_artf_id_ck;

--changeset clive:create_constraint_other_orac_core_kn_artf_hash_ck context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_ARTF_HASH_CK';
alter table orac_core.knowledge_artefacts add constraint kn_artf_hash_ck
  check (regexp_like(content_sha256, '^[0-9a-f]{64}$'));
--rollback alter table orac_core.knowledge_artefacts drop constraint kn_artf_hash_ck;

--changeset clive:create_constraint_other_orac_core_kn_artf_storage_key_ck context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_ARTF_STORAGE_KEY_CK';
alter table orac_core.knowledge_artefacts add constraint kn_artf_storage_key_ck
  check (storage_key = 'sha256:' || content_sha256);
--rollback alter table orac_core.knowledge_artefacts drop constraint kn_artf_storage_key_ck;

--changeset clive:create_constraint_other_orac_core_kn_artf_size_ck context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_ARTF_SIZE_CK';
alter table orac_core.knowledge_artefacts add constraint kn_artf_size_ck
  check (byte_size >= 0);
--rollback alter table orac_core.knowledge_artefacts drop constraint kn_artf_size_ck;

--changeset clive:create_constraint_other_orac_core_kn_artf_role_ck context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_ARTF_ROLE_CK';
alter table orac_core.knowledge_artefacts add constraint kn_artf_role_ck
  check (artefact_role_code in ('PRIMARY', 'MANIFEST', 'TABLE', 'METADATA'));
--rollback alter table orac_core.knowledge_artefacts drop constraint kn_artf_role_ck;

--changeset clive:create_constraint_other_orac_core_kn_artf_ordinal_ck context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_ARTF_ORDINAL_CK';
alter table orac_core.knowledge_artefacts add constraint kn_artf_ordinal_ck
  check (member_ordinal > 0);
--rollback alter table orac_core.knowledge_artefacts drop constraint kn_artf_ordinal_ck;

--changeset clive:create_constraint_other_orac_core_kn_artf_logical_name_ck context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'KN_ARTF_LOGICAL_NAME_CK';
alter table orac_core.knowledge_artefacts add constraint kn_artf_logical_name_ck
  check (regexp_like(logical_name, '^[a-z0-9][a-z0-9._-]{0,199}$'));
--rollback alter table orac_core.knowledge_artefacts drop constraint kn_artf_logical_name_ck;
