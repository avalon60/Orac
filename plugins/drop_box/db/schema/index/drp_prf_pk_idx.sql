--liquibase formatted sql

--changeset clive:drop_box_index_drp_prf_pk_idx context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_indexes where owner = 'ORAC_DROPBOX' and index_name = 'DRP_PRF_PK_IDX'
create unique index orac_dropbox.drp_prf_pk_idx on orac_dropbox.drop_processing_profile (profile_code);

--rollback drop index orac_dropbox.drp_prf_pk_idx;
