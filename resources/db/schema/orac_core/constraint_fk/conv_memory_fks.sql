--liquibase formatted sql

--changeset clive:create_constraint_orac_core_conv_memreq_convs_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_MEMREQ_CONVS_FK1';
alter table orac_core.conversation_memory_requests add constraint conv_memreq_convs_fk1
  foreign key (conversation_id) references orac_core.conversations (conversation_id) on delete cascade;
--rollback alter table orac_core.conversation_memory_requests drop constraint conv_memreq_convs_fk1;

--changeset clive:create_constraint_orac_core_conv_sumchk_convs_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_SUMCHK_CONVS_FK1';
alter table orac_core.conversation_summary_checkpoints add constraint conv_sumchk_convs_fk1
  foreign key (conversation_id) references orac_core.conversations (conversation_id) on delete cascade;
--rollback alter table orac_core.conversation_summary_checkpoints drop constraint conv_sumchk_convs_fk1;

--changeset clive:create_constraint_orac_core_conv_memreq_sumchk_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_MEMREQ_SUMCHK_FK1';
alter table orac_core.conversation_memory_requests add constraint conv_memreq_sumchk_fk1
  foreign key (checkpoint_id) references orac_core.conversation_summary_checkpoints (checkpoint_id);
--rollback alter table orac_core.conversation_memory_requests drop constraint conv_memreq_sumchk_fk1;

--changeset clive:create_constraint_orac_core_conv_sumsrc_sumchk_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_SUMSRC_SUMCHK_FK1';
alter table orac_core.conversation_summary_sources add constraint conv_sumsrc_sumchk_fk1
  foreign key (checkpoint_id) references orac_core.conversation_summary_checkpoints (checkpoint_id) on delete cascade;
--rollback alter table orac_core.conversation_summary_sources drop constraint conv_sumsrc_sumchk_fk1;

--changeset clive:create_constraint_orac_core_conv_sumsrc_mesgs_fk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_SUMSRC_MESGS_FK1';
alter table orac_core.conversation_summary_sources add constraint conv_sumsrc_mesgs_fk1
  foreign key (message_id) references orac_core.messages (message_id) on delete cascade;
--rollback alter table orac_core.conversation_summary_sources drop constraint conv_sumsrc_mesgs_fk1;
