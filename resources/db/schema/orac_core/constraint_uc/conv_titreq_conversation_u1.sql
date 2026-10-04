--liquibase formatted sql
--changeset clive:create_uc_orac_core_conv_titreq_conversation context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_TITREQ_CONVERSATION_U1';
alter table orac_core.conversation_title_requests add constraint conv_titreq_conversation_u1
unique (conversation_id);
--rollback alter table orac_core.conversation_title_requests drop constraint conv_titreq_conversation_u1;
