--liquibase formatted sql

--changeset clive:drop_box_add_location_classification_tags context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_LOCATION' and column_name = 'CLASSIFICATION_TAGS_JSON'
alter table orac_dropbox.drop_location add (
  classification_tags_json clob
    constraint drp_loc_tags_json_ck check (classification_tags_json is json)
);
--rollback alter table orac_dropbox.drop_location drop column classification_tags_json;

--changeset clive:drop_box_add_job_classification_tags context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_JOB' and column_name = 'EFFECTIVE_CLASSIFICATION_TAGS_JSON'
alter table orac_dropbox.drop_job add (
  effective_classification_tags_json clob
    constraint drp_job_tags_json_ck check (effective_classification_tags_json is json)
);
--rollback alter table orac_dropbox.drop_job drop column effective_classification_tags_json;

--changeset clive:drop_box_add_job_conversion_retry context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(*) from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_JOB' and column_name = 'CONVERSION_ATTEMPTS'
alter table orac_dropbox.drop_job add (
  conversion_attempts number default 0 not null,
  next_attempt_on timestamp with time zone,
  failure_reason_code varchar2(100 char),
  last_warning_on timestamp with time zone
);
--rollback alter table orac_dropbox.drop_job drop (conversion_attempts, next_attempt_on, failure_reason_code, last_warning_on);

--changeset clive:drop_box_make_profile_instruction_optional context:plugin,prod labels:plugin,drop_box stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:N select nullable from all_tab_columns where owner = 'ORAC_DROPBOX' and table_name = 'DROP_PROCESSING_PROFILE' and column_name = 'DEFAULT_INSTRUCTION';
alter table orac_dropbox.drop_processing_profile modify (default_instruction null);
--rollback update orac_dropbox.drop_processing_profile set default_instruction = to_clob('Compatibility classification; no behavioural authority.') where default_instruction is null; alter table orac_dropbox.drop_processing_profile modify (default_instruction not null);
