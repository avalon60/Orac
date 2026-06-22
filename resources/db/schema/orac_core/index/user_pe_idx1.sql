--liquibase formatted sql

--changeset clive:create_index_orac_core_index_user_pe_idx1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'USER_PE_IDX1';
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create index orac_core.user_pe_idx1
  on orac_core.user_prompt_elements
  (
    user_id asc,
    category_code asc
  )
;

--rollback drop index orac_core.user_pe_idx1;
