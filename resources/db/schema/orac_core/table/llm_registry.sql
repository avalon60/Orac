-- __author__: clive bostock
-- __date__: 2025-10-19
-- __description__: generated/synchronised by Cline; one object per file

create table orac.llm_registry (
  llm_id             number generated always as identity not null,
  name               varchar2(100 char) not null,
  provider           varchar2(100 char),
  model              varchar2(200 char) not null,
  context_policy     varchar2(20 char) not null,
  max_context_tokens number,
  is_enabled         char(1) default 'y' not null,
  properties         json,
  created_on         timestamp(6) with local time zone default on null systimestamp not null,
  created_by         varchar2(128 char) default on null coalesce(
                        sys_context('apex$session','app_user'),
                        sys_context('userenv','proxy_user'),
                        sys_context('userenv','session_user'),
                        user
                      ) not null,
  updated_on         timestamp(6) with local time zone,
  updated_by         varchar2(128 char),
  row_version        number default 1 not null
);
