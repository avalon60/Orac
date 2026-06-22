--liquibase formatted sql

--changeset clive:create_index_orac_core_index_convs_uk1_idx context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'CONVS_UK1_IDX';
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create unique index orac_core.convs_uk1_idx
  on orac_core.conversations
  (
    session_id asc
  )
;

--rollback drop index orac_core.convs_uk1_idx;
