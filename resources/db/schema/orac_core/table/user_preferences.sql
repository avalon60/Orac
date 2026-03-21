-- __author__: clive bostock
-- __date__: 2025-10-19
-- __description__: generated/synchronised by Cline; one object per file

create table orac.user_preferences (
  pref_id     number generated always as identity not null,
  user_id     number not null,
  pref_key    varchar2(100 char) not null,
  pref_value  json,
  value_type  varchar2(8 char) default 'string' not null,
  created_on  timestamp with local time zone default on null systimestamp not null,
  created_by  varchar2(128 char) default on null coalesce(
                sys_context('apex$session','app_user'),
                sys_context('userenv','proxy_user'),
                sys_context('userenv','session_user'),
                user
              ) not null,
  updated_on  timestamp with local time zone,
  updated_by  varchar2(128 char),
  row_version number default 1 not null
)
  logging
  no inmemory
;
