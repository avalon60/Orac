--liquibase formatted sql

--changeset clive:create_constraint_orac_core_conv_memreq_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_MEMREQ_UK1';
alter table orac_core.conversation_memory_requests add constraint conv_memreq_uk1
  unique (conversation_id, first_turn_index, last_turn_index, materialisation_profile, prompt_version);
--rollback alter table orac_core.conversation_memory_requests drop constraint conv_memreq_uk1;

--changeset clive:create_constraint_orac_core_conv_sumchk_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_SUMCHK_UK1';
alter table orac_core.conversation_summary_checkpoints add constraint conv_sumchk_uk1
  unique (conversation_id, first_turn_index, last_turn_index, materialisation_profile, prompt_version);
--rollback alter table orac_core.conversation_summary_checkpoints drop constraint conv_sumchk_uk1;

--changeset clive:create_constraint_orac_core_conv_sumsrc_uk1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_SUMSRC_UK1';
alter table orac_core.conversation_summary_sources add constraint conv_sumsrc_uk1
  unique (checkpoint_id, message_id);
--rollback alter table orac_core.conversation_summary_sources drop constraint conv_sumsrc_uk1;

--changeset clive:create_constraint_orac_core_conv_sumsrc_uk2 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_SUMSRC_UK2';
alter table orac_core.conversation_summary_sources add constraint conv_sumsrc_uk2
  unique (checkpoint_id, source_position);
--rollback alter table orac_core.conversation_summary_sources drop constraint conv_sumsrc_uk2;
