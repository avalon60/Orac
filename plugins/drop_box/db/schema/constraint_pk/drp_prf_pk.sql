--liquibase formatted sql

--changeset clive:drop_box_constraint_pk_drp_prf_pk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_PRF_PK'
alter table orac_dropbox.drop_processing_profile add constraint drp_prf_pk primary key (profile_code) using index orac_dropbox.drp_prf_pk_idx;

--rollback alter table orac_dropbox.drop_processing_profile drop constraint drp_prf_pk;
