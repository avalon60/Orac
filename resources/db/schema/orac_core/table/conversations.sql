-- __author__: clive bostock
-- __date__: 2025-10-19
-- __description__: generated/synchronised by Cline; one object per file

create table orac.conversations (
  conversation_id number generated always as identity not null,
  user_id         number not null,
  session_id      varchar2(64 char) not null,
  llm_id          number,
  title           varchar2(200 char) default on null 'Brief exchange...',
  state           varchar2(20 char) default 'open' not null,
  created_on      timestamp with local time zone default on null systimestamp not null,
  created_by      varchar2(128 char) default on null coalesce(
                     sys_context('apex$session','app_user'),
                     sys_context('userenv','proxy_user'),
                     sys_context('userenv','session_user'),
                     user
                   ) not null,
  updated_on      timestamp with local time zone,
  updated_by      varchar2(128 char),
  row_version     number default 1 not null
);
