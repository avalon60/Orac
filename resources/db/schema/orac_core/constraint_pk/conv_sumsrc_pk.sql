--liquibase formatted sql
--changeset clive:create_constraint_orac_core_conv_sumsrc_pk context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_SUMSRC_PK';
alter table orac_core.conversation_summary_sources add constraint conv_sumsrc_pk
  primary key (checkpoint_source_id);
--rollback alter table orac_core.conversation_summary_sources drop constraint conv_sumsrc_pk;
