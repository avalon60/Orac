--liquibase formatted sql

--changeset clive:create_table_orac_core_table_users context:core labels:core stripComments:false
--preconditions onFail:HALT onError:HALT
--precondition-sql-check expectedResult:0 select count(1) from all_tables where owner = 'ORAC_CORE' and table_name = 'USERS';
-- __author__: clive
-- __date__: 2026-03-21
-- __description__: generated/synchronised by split_ddl; one object per file


create table orac_core.users
(
  user_id      number generated always as identity not null,
  username     varchar2(100 char) not null,
  display_name varchar2(200 char),
  email        varchar2(320 char),
  is_active    char(1 char) default 'Y' not null,
  created_on   timestamp default on null systimestamp not null,
  created_by   varchar2(128 char) default on null coalesce(
                 sys_context('apex$session', 'app_user'),
                 sys_context('userenv', 'proxy_user'),
                 sys_context('userenv', 'session_user'),
                 user
               ) not null,
  updated_on   timestamp,
  updated_by   varchar2(128 char),
  row_version  number default 1 not null
)
;

--rollback drop table orac_core.users purge;
