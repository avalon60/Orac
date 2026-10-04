--liquibase formatted sql
--changeset clive:create_status_check_orac_core_conv_titreq context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_TITREQ_STATUS_CK';
alter table orac_core.conversation_title_requests add constraint conv_titreq_status_ck
check (status_code in ('PENDING', 'PROCESSING', 'COMPLETED', 'RETRY', 'FAILED'));
--rollback alter table orac_core.conversation_title_requests drop constraint conv_titreq_status_ck;

--changeset clive:create_attempts_check_orac_core_conv_titreq context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_CORE' and constraint_name = 'CONV_TITREQ_ATTEMPTS_CK';
alter table orac_core.conversation_title_requests add constraint conv_titreq_attempts_ck
check (attempts >= 0 and max_attempts between 1 and 10);
--rollback alter table orac_core.conversation_title_requests drop constraint conv_titreq_attempts_ck;
