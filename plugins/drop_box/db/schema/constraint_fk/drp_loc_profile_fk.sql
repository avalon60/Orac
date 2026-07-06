--liquibase formatted sql

--changeset clive:drop_box_constraint_fk_drp_loc_profile_fk context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_LOC_PROFILE_FK'
alter table orac_dropbox.drop_location add constraint drp_loc_profile_fk
  foreign key (processing_profile)
  references orac_dropbox.drop_processing_profile (profile_code);

--rollback alter table orac_dropbox.drop_location drop constraint drp_loc_profile_fk;
