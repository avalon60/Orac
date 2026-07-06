--liquibase formatted sql

--changeset clive:drop_box_constraint_pk_drp_loc_pk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_LOC_PK'
alter table orac_dropbox.drop_location add constraint drp_loc_pk primary key (drop_location_id) using index orac_dropbox.drp_loc_pk_idx;

--rollback alter table orac_dropbox.drop_location drop constraint drp_loc_pk;
