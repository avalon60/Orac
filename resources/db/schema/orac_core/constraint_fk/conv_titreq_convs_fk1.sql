--liquibase formatted sql
--changeset clive:create_fk_orac_core_conv_titreq_convs context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_TITREQ_CONVS_FK1';
alter table orac_core.conversation_title_requests add constraint conv_titreq_convs_fk1
foreign key (conversation_id) references orac_core.conversations (conversation_id) on delete cascade;
--rollback alter table orac_core.conversation_title_requests drop constraint conv_titreq_convs_fk1;
