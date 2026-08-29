--liquibase formatted sql

--changeset clive:create_index_orac_core_conv_memreq_ix1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'CONV_MEMREQ_IX1';
create index orac_core.conv_memreq_ix1 on orac_core.conversation_memory_requests
  (status_code, next_attempt_on, memory_request_id);
--rollback drop index orac_core.conv_memreq_ix1;

--changeset clive:create_index_orac_core_conv_sumchk_ix1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'CONV_SUMCHK_IX1';
create index orac_core.conv_sumchk_ix1 on orac_core.conversation_summary_checkpoints
  (conversation_id, created_on);
--rollback drop index orac_core.conv_sumchk_ix1;

--changeset clive:create_index_orac_core_conv_sumsrc_ix1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'CONV_SUMSRC_IX1';
create index orac_core.conv_sumsrc_ix1 on orac_core.conversation_summary_sources
  (message_id);
--rollback drop index orac_core.conv_sumsrc_ix1;
