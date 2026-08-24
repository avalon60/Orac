--liquibase formatted sql
-- Author: clive
-- Date: 2026-08-12
-- Description: Creates indexes for immutable knowledge artefacts.
-- Codex-assisted generated/modified.
-- Codex SDK reviewability guardrails followed.

--changeset clive:create_index_orac_core_kn_artf_pk context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_ARTF_PK';
create unique index orac_core.kn_artf_pk
  on orac_core.knowledge_artefacts (artefact_id);
--rollback drop index orac_core.kn_artf_pk;

--changeset clive:create_index_orac_core_kn_artf_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_ARTF_UK1_IDX';
create unique index orac_core.kn_artf_uk1_idx
  on orac_core.knowledge_artefacts (extraction_id, logical_name);
--rollback drop index orac_core.kn_artf_uk1_idx;

--changeset clive:create_index_orac_core_kn_artf_uk2_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_ARTF_UK2_IDX';
create unique index orac_core.kn_artf_uk2_idx
  on orac_core.knowledge_artefacts (extraction_id, member_ordinal);
--rollback drop index orac_core.kn_artf_uk2_idx;

--changeset clive:create_index_orac_core_kn_artf_uk3_idx context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_ARTF_UK3_IDX';
create unique index orac_core.kn_artf_uk3_idx
  on orac_core.knowledge_artefacts (extraction_id, artefact_id);
--rollback drop index orac_core.kn_artf_uk3_idx;

--changeset clive:create_index_orac_core_kn_artf_fidx1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_ARTF_FIDX1';
create unique index orac_core.kn_artf_fidx1
  on orac_core.knowledge_artefacts (
    case when artefact_role_code in ('PRIMARY', 'MANIFEST') then extraction_id end
  );
--rollback drop index orac_core.kn_artf_fidx1;

--changeset clive:create_index_orac_core_kn_artf_idx1 context:core labels:core stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'KN_ARTF_IDX1';
create index orac_core.kn_artf_idx1
  on orac_core.knowledge_artefacts (storage_key);
--rollback drop index orac_core.kn_artf_idx1;
