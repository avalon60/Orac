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
