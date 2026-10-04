--liquibase formatted sql
--changeset clive:create_pk_orac_core_conv_titreq context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_TITREQ_PK';
alter table orac_core.conversation_title_requests add constraint conv_titreq_pk
primary key (title_request_id);
--rollback alter table orac_core.conversation_title_requests drop constraint conv_titreq_pk;
