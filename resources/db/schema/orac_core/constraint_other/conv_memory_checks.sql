--liquibase formatted sql

--changeset clive:create_constraint_orac_core_conv_memreq_ck1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_MEMREQ_CK1';
alter table orac_core.conversation_memory_requests add constraint conv_memreq_ck1
  check (status_code in ('PENDING', 'RETRY_WAIT', 'COMPLETED', 'FAILED'));
--rollback alter table orac_core.conversation_memory_requests drop constraint conv_memreq_ck1;

--changeset clive:create_constraint_orac_core_conv_memreq_ck2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_MEMREQ_CK2';
alter table orac_core.conversation_memory_requests add constraint conv_memreq_ck2
  check (first_turn_index > 0 and last_turn_index >= first_turn_index and attempt_count >= 0 and max_attempts > 0);
--rollback alter table orac_core.conversation_memory_requests drop constraint conv_memreq_ck2;

--changeset clive:create_constraint_orac_core_conv_sumchk_ck1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_SUMCHK_CK1';
alter table orac_core.conversation_summary_checkpoints add constraint conv_sumchk_ck1
  check (first_turn_index > 0 and last_turn_index >= first_turn_index and embedding_dimensions > 0 and distance_metric = 'COSINE');
--rollback alter table orac_core.conversation_summary_checkpoints drop constraint conv_sumchk_ck1;

--changeset clive:create_constraint_orac_core_conv_sumsrc_ck1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_SUMSRC_CK1';
alter table orac_core.conversation_summary_sources add constraint conv_sumsrc_ck1
  check (source_position > 0 and turn_index > 0 and message_row_version > 0);
--rollback alter table orac_core.conversation_summary_sources drop constraint conv_sumsrc_ck1;
