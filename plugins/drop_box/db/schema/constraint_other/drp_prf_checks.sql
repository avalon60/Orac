--liquibase formatted sql

--changeset clive:drop_box_constraint_other_drp_prf_checks_1 context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_PRF_ACTIVE_CK'
alter table orac_dropbox.drop_processing_profile add constraint drp_prf_active_ck
  check (active_yn in ('Y', 'N'));

--rollback alter table orac_dropbox.drop_processing_profile drop constraint drp_prf_active_ck;

--changeset clive:drop_box_constraint_other_drp_prf_checks_2 context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_PRF_SYSTEM_CK'
alter table orac_dropbox.drop_processing_profile add constraint drp_prf_system_ck
  check (system_yn in ('Y', 'N'));

--rollback alter table orac_dropbox.drop_processing_profile drop constraint drp_prf_system_ck;

--changeset clive:drop_box_constraint_other_drp_prf_checks_3 context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_constraints where owner = 'ORAC_DROPBOX' and constraint_name = 'DRP_PRF_CODE_CK'
alter table orac_dropbox.drop_processing_profile add constraint drp_prf_code_ck
  check (regexp_like(profile_code, '^[a-z][a-z0-9_]{1,99}$'));

--rollback alter table orac_dropbox.drop_processing_profile drop constraint drp_prf_code_ck;
