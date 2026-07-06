--liquibase formatted sql

--changeset clive:drop_box_constraint_other_drp_loc_checks_1 context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_LOC_ENABLED_CK'
alter table orac_dropbox.drop_location add constraint drp_loc_enabled_ck check (enabled_yn in ('Y', 'N'));

--rollback alter table orac_dropbox.drop_location drop constraint drp_loc_enabled_ck;

--changeset clive:drop_box_constraint_other_drp_loc_checks_2 context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_LOC_RECURSIVE_CK'
alter table orac_dropbox.drop_location add constraint drp_loc_recursive_ck check (recursive_yn in ('Y', 'N'));

--rollback alter table orac_dropbox.drop_location drop constraint drp_loc_recursive_ck;

--changeset clive:drop_box_constraint_other_drp_loc_checks_3 context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_LOC_MOVE_CK'
alter table orac_dropbox.drop_location add constraint drp_loc_move_ck check (move_processed_yn in ('Y', 'N'));

--rollback alter table orac_dropbox.drop_location drop constraint drp_loc_move_ck;
