-- __author__: clive bostock
-- __date__: 2025-10-19
-- __description__: generated/synchronised by Cline; one object per file

create table orac.users (
  user_id      number generated always as identity not null,
  username     varchar2(100 char) not null,
  display_name varchar2(200 char),
  email        varchar2(320 char),
  is_active    char(1) default 'y' not null,
  created_on   timestamp(6) with local time zone default on null systimestamp not null,
  created_by   varchar2(128 char) default on null coalesce(
                  sys_context('apex$session','app_user'),
                  sys_context('userenv','proxy_user'),
                  sys_context('userenv','session_user'),
                  user
                ) not null,
  updated_on   timestamp(6) with local time zone,
  updated_by   varchar2(128 char),
  row_version  number default 1 not null
);
