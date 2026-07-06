--liquibase formatted sql

--changeset clive:drop_box_table_drop_processing_profile context:plugin,prod labels:plugin stripComments:false
--preconditions onFail:MARK_RAN onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_DROPBOX' and table_name = 'DROP_PROCESSING_PROFILE'
create table orac_dropbox.drop_processing_profile
(
  profile_code        varchar2(100 char) not null,
  display_name        varchar2(200 char) not null,
  description         varchar2(1000 char) not null,
  default_instruction clob not null,
  active_yn           varchar2(1 char) default 'Y' not null,
  system_yn           varchar2(1 char) default 'N' not null,
  sort_order          number default 100 not null,
  created_by          varchar2(128 char) default coalesce(
                        sys_context('apex$session', 'app_user'),
                        sys_context('userenv', 'proxy_user'),
                        sys_context('userenv', 'session_user'),
                        user
                      ) not null,
  created_on          timestamp with time zone default systimestamp not null,
  updated_by          varchar2(128 char) default coalesce(
                        sys_context('apex$session', 'app_user'),
                        sys_context('userenv', 'proxy_user'),
                        sys_context('userenv', 'session_user'),
                        user
                      ) not null,
  updated_on          timestamp with time zone default systimestamp not null,
  row_version         number default 1 not null
)
logging
no inmemory;

--rollback drop table orac_dropbox.drop_processing_profile;
