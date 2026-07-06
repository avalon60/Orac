--liquibase formatted sql

--changeset clive:drop_box_constraint_uc_drp_loc_code_uk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_LOC_CODE_UK'
alter table orac_dropbox.drop_location add constraint drp_loc_code_uk unique (location_code);

--rollback alter table orac_dropbox.drop_location drop constraint drp_loc_code_uk;
