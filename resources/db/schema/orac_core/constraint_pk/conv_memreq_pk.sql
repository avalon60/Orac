--liquibase formatted sql
--changeset clive:create_constraint_orac_core_conv_memreq_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_MEMREQ_PK';
alter table orac_core.conversation_memory_requests add constraint conv_memreq_pk
  primary key (memory_request_id);
--rollback alter table orac_core.conversation_memory_requests drop constraint conv_memreq_pk;
