--liquibase formatted sql
--changeset clive:create_index_orac_core_conv_titreq_claim_i1 context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_CORE' and index_name = 'CONV_TITREQ_CLAIM_I1';
create index orac_core.conv_titreq_claim_i1 on orac_core.conversation_title_requests
(status_code, next_attempt_on, lease_expires_on);
--rollback drop index orac_core.conv_titreq_claim_i1;
